import requests
import os
import json
from datetime import datetime, timedelta, timezone

# ================= KONFIGURACJA =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")
KEYS_POOL = [os.getenv(f"ODDS_KEY{i}") for i in ["", "_2", "_3", "_4", "_5"]]
API_KEYS = [k for k in KEYS_POOL if k]

# PROGI KURSOWE
MIN_SINGLE_ODD = 1.45
MAX_SINGLE_ODD = 1.85
SINGLE_THRESHOLD = 1.90  # Powyżej tego kursu gramy jako SINGLE
TAX_RATE = 0.88

STAKE_STANDARD = 50.0    # Dla Double
STAKE_SINGLE = 80.0      # Dla Single (wyższa pewność)

MAX_VARIANCE = 0.06
MIN_BOOKMAKERS = 8

SPORTS_CONFIG = {
    "soccer_epl": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League", 
    "soccer_spain_la_liga": "🇪🇸 La Liga",
    "soccer_germany_bundesliga": "🇩🇪 Bundesliga", 
    "soccer_italy_serie_a": "🇮🇹 Serie A",
    "soccer_france_ligue_one": "🇫🇷 Ligue 1", 
    "soccer_poland_ekstraklasa": "🇵🇱 Ekstraklasa",
    "soccer_netherlands_ere_divisie": "🇳🇱 Eredivisie",
    "soccer_portugal_primeira_liga": "🇵🇹 Primeira Liga",
    "soccer_uefa_champions_league": "🇪🇺 Liga Mistrzów", 
    "soccer_uefa_europa_league": "🇪🇺 Liga Europy"
}

COUPONS_FILE = "coupons_hybrid.json"

# ================= FUNKCJE SYSTEMOWE =================

def load_coupons():
    if not os.path.exists(COUPONS_FILE): return []
    try:
        with open(COUPONS_FILE, "r") as f: return json.load(f)
    except: return []

def save_coupons(coupons):
    with open(COUPONS_FILE, "w") as f: 
        json.dump(coupons[-500:], f, indent=4)

def send_msg(text):
    if not T_TOKEN or not T_CHAT: return
    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
    try: requests.post(url, json={"chat_id": T_CHAT, "text": text, "parse_mode": "Markdown"}, timeout=15)
    except: pass

def check_results():
    coupons = load_coupons()
    updated = False
    now = datetime.now(timezone.utc)
    for c in coupons:
        if c.get("status") != "pending": continue
        end_time = datetime.fromisoformat(c["end_time"])
        if now > end_time + timedelta(hours=4):
            for key in API_KEYS:
                try:
                    r = requests.get(f"https://api.the-odds-api.com/v4/sports/{c['sport_key']}/scores/", 
                                   params={"apiKey": key, "daysFrom": 3}, timeout=15)
                    if r.status_code == 200:
                        scores = r.json()
                        matches_found, wins = 0, 0
                        for m_saved in c["matches"]:
                            for s in scores:
                                if s["id"] == m_saved["id"] and s.get("completed"):
                                    matches_found += 1
                                    sl = s.get("scores", [])
                                    if len(sl) >= 2:
                                        h, a = int(sl[0]["score"]), int(sl[1]["score"])
                                        winner = s["home_team"] if h > a else (s["away_team"] if a > h else "Remis")
                                        if winner == m_saved["picked"]: wins += 1
                        
                        if matches_found == len(c["matches"]):
                            c["status"] = "win" if wins == len(c["matches"]) else "loss"
                            updated = True
                            icon = "✅" if c["status"] == "win" else "❌"
                            val = round(c['win_val'] - c['stake'], 2) if c["status"] == "win" else -c['stake']
                            send_msg(f"{icon} **KUPON ROZLICZONY**\nWynik: `{val:+.2f} PLN`")
                        break
                except: continue
    if updated: save_coupons(coupons)

# ================= ANALIZA I GENEROWANIE KUPONÓW =================

def run():
    send_msg("🤖 **HYBRYDOWY SYSTEM AKTYWNY**\nSkanowanie: Single 2.0+ oraz Double 1.45-1.75...")
    check_results()
    
    now_utc = datetime.now(timezone.utc)
    coupons_db = load_coupons()
    sent_ids = [m["id"] for c in coupons_db for m in c["matches"]]
    all_picks = []

    for sport_key, sport_label in SPORTS_CONFIG.items():
        matches = None
        for key in API_KEYS:
            try:
                r = requests.get(f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/",
                               params={"apiKey": key, "regions": "eu", "markets": "h2h"}, timeout=15)
                if r.status_code == 200:
                    matches = r.json()
                    break
            except: continue
            
        if not matches: continue

        for m in matches:
            if m["id"] in sent_ids or len(m.get("bookmakers", [])) < MIN_BOOKMAKERS: continue
            
            m_dt_utc = datetime.fromisoformat(m["commence_time"].replace('Z', '+00:00'))
            if m_dt_utc < now_utc or m_dt_utc > (now_utc + timedelta(hours=48)): continue

            h_t, a_t = m["home_team"], m["away_team"]
            h_o, a_o = [], []
            
            for bm in m.get("bookmakers", []):
                for market in bm.get("markets", []):
                    if market["key"] == "h2h":
                        for o in market["outcomes"]:
                            if o["name"] == h_t: h_o.append(o["price"])
                            if o["name"] == a_t: a_o.append(o["price"])
            
            if len(h_o) < MIN_BOOKMAKERS: continue
            avg_h, avg_a = sum(h_o)/len(h_o), sum(a_o)/len(a_o)
            
            pick = None
            # Logika wyboru: szukamy faworyta w naszym zakresie
            if MIN_SINGLE_ODD <= avg_h <= MAX_SINGLE_ODD and (max(h_o)-min(h_o))/avg_h <= MAX_VARIANCE:
                pick = {"id": m["id"], "team": h_t, "odd": avg_h, "league": sport_label, "key": sport_key, "picked": h_t, "date": m_dt_utc, "home": True, "vs": a_t}
            elif MIN_SINGLE_ODD <= avg_a <= MAX_SINGLE_ODD and (max(a_o)-min(a_o))/avg_a <= MAX_VARIANCE:
                pick = {"id": m["id"], "team": a_t, "odd": avg_a, "league": sport_label, "key": sport_key, "picked": a_t, "date": m_dt_utc, "home": False, "vs": h_t}
            
            if pick: all_picks.append(pick)

    # --- SELEKCJA HYBRYDOWA ---
    
    # 1. Wysyłamy SINGLE (kursy >= 1.90 lub wybrane mocne typy)
    singles = [p for p in all_picks if p['odd'] >= SINGLE_THRESHOLD]
    for s in singles:
        win = round(STAKE_SINGLE * TAX_RATE * s['odd'], 2)
        msg = (f"🎯 **TYP SINGLE (Value)**\n━━━━━━━━━━━━━━━\n"
               f"🏟 **{s['team']}** {'🏠' if s['home'] else '🚌'}\n🏆 {s['league']}\n"
               f"📈 Kurs: `{s['odd']:.2f}`\n━━━━━━━━━━━━━━━\n"
               f"💰 Stawka: `{STAKE_SINGLE} PLN` | Wygrana: `{win} PLN`")
