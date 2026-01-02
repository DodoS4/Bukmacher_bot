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
MIN_SINGLE_ODD = 1.35
MAX_SINGLE_ODD = 1.95
SINGLE_THRESHOLD = 2.05  
TAX_RATE = 0.88

STAKE_STANDARD = 50.0    
STAKE_SINGLE = 80.0      

# FILTRY
MAX_VARIANCE = 0.12
MIN_BOOKMAKERS = 4

# KONFIGURACJA LIG Z IKONAMI
SPORTS_CONFIG = {
    "soccer_epl": "⚽ 🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League", 
    "soccer_spain_la_liga": "⚽ 🇪🇸 La Liga",
    "soccer_germany_bundesliga": "⚽ 🇩🇪 Bundesliga", 
    "soccer_italy_serie_a": "⚽ 🇮🇹 Serie A",
    "soccer_france_ligue_one": "⚽ 🇫🇷 Ligue 1", 
    "soccer_poland_ekstraklasa": "⚽ 🇵🇱 Ekstraklasa",
    "soccer_netherlands_ere_divisie": "⚽ 🇳🇱 Eredivisie",
    "soccer_portugal_primeira_liga": "⚽ 🇵🇹 Primeira Liga",
    "soccer_uefa_champions_league": "⚽ 🇪🇺 Liga Mistrzów", 
    "soccer_uefa_europa_league": "⚽ 🇪🇺 Liga Europy",
    "basketball_nba": "🏀 NBA",
    "icehockey_nhl": "🏒 NHL"
}

COUPONS_FILE = "coupons.json"

# ================= FUNKCJE POMOCNICZE =================

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
    try: 
        requests.post(url, json={"chat_id": T_CHAT, "text": text, "parse_mode": "Markdown"}, timeout=15)
    except: 
        pass

# ================= RAPORTOWANIE Z ANALIZĄ SPORTÓW =================

def send_daily_report():
    coupons = load_coupons()
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)
    
    completed_today = [c for c in coupons if c.get("status") in ["win", "loss"] 
                       and "end_time" in c 
                       and datetime.fromisoformat(c["end_time"]) > yesterday]
    
    if not completed_today:
        send_msg("📊 *RAPORT DZIENNY*\n━━━━━━━━━━━━━━━\nBrak rozliczonych kuponów w ostatnich 24h.")
        return

    total_stake = sum(c["stake"] for c in completed_today)
    total_win = sum(c["win_val"] if c["status"] == "win" else 0 for c in completed_today)
    profit = total_win - total_stake
    wins = len([c for c in completed_today if c["status"] == "win"])
    total = len(completed_today)
    accuracy = (wins / total) * 100 if total > 0 else 0
    
    # Analiza per sport
    stats_per_sport = {}
    for c in completed_today:
        # Sprawdzamy ikonę z pierwszego meczu na kuponie
        first_match_id = c["matches"][0]["id"]
        # Szukamy ikony w SPORTS_CONFIG na podstawie zapisanego league label
        sport_icon = "❓"
        for key, label in SPORTS_CONFIG.items():
            if any(m["sport_key"] == key for m in c["matches"]):
                sport_icon = label[0] # Pobiera pierwszy znak czyli emoji
                break
        
        c_profit = (c["win_val"] - c["stake"]) if c["status"] == "win" else -c["stake"]
        stats_per_sport[sport_icon] = stats_per_sport.get(sport_icon, 0) + c_profit

    sport_report = ""
    for icon, val in stats_per_sport.items():
        sport_report += f"{icon} : `{val:+.2f} PLN`\n"

    icon_overall = "📈" if profit >= 0 else "📉"
    
    report = (
        f"📊 *RAPORT DZIENNY*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ Kupony: `{total}` | 🎯 `{accuracy:.1f}%`\n"
        f"💰 Obrót: `{total_stake:.2f} PLN`\n"
        f"{icon_overall} **Bilans całkowity:** `{profit:+.2f} PLN`\n\n"
        f"🏆 *Wyniki wg dyscyplin:*\n"
        f"{sport_report}"
        f"━━━━━━━━━━━━━━━━━━━━"
    )
    send_msg(report)

# ================= LOGIKA ROZLICZANIA =================

def check_results():
    coupons = load_coupons()
    updated = False
    now = datetime.now(timezone.utc)
    
    for c in coupons:
        if c.get("status") != "pending": continue
        end_time = datetime.fromisoformat(c["end_time"])
        if now < end_time + timedelta(hours=4): continue

        matches_results = []
        for m_saved in c["matches"]:
            s_key = m_saved.get("sport_key")
            if not s_key: continue
            for key in API_KEYS:
                try:
                    r = requests.get(f"https://api.the-odds-api.com/v4/sports/{s_key}/scores/", 
                                   params={"apiKey": key, "daysFrom": 3}, timeout=15)
                    if r.status_code == 200:
                        scores = r.json()
                        s_data = next((s for s in scores if s["id"] == m_saved["id"] and s.get("completed")), None)
                        if s_data:
                            sl = s_data.get("scores", [])
                            if len(sl) >= 2:
                                h_score = int(next(x['score'] for x in sl if x['name'] == s_data['home_team']))
                                a_score = int(next(x['score'] for x in sl if x['name'] == s_data['away_team']))
                                winner = s_data["home_team"] if h_score > a_score else (s_data["away_team"] if a_score > h_score else "Remis")
                                matches_results.append(winner == m_saved["picked"])
                        break
                except: continue
        
        if len(matches_results) == len(c["matches"]):
            c["status"] = "win" if all(matches_results) else "loss"
            updated = True
            icon = "✅" if c["status"] == "win" else "❌"
            val = round(c['win_val'] - c['stake'], 2) if c["status"] == "win" else -c['stake']
            send_msg(f"{icon} *KUPON ROZLICZONY*\n━━━━━━━━━━━━━━━\nBilans: `{val:+.2f} PLN`")
            
    if updated: save_coupons(coupons)

# ================= ANALIZA I GENEROWANIE KUPONÓW =================

def run():
    print("🚀 Start bota...")
    check_results()
    now_utc = datetime.now(timezone.utc)
    coupons_db = load_coupons()
    sent_ids = [m["id"] for c in coupons_db for m in c["matches"]]
    all_picks = []

    for sport_key, league_label in SPORTS_CONFIG.items():
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
            if m["id"] in sent_ids: continue
            if len(m.get("bookmakers", [])) < MIN_BOOKMAKERS: continue
            
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
            
            if not h_o or not a_o: continue
            avg_h, avg_a = sum(h_o)/len(h_o), sum(a_o)/len(a_o)
            var_h, var_a = (max(h_o)-min(h_o))/avg_h, (max(a_o)-min(a_o))/avg_a
            
            common_data = {"id": m["id"], "league": league_label, "key": sport_key, "date": m_dt_utc, "home_name": h_t, "away_name": a_t}
            
            pick = None
            if MIN_SINGLE_ODD <= avg_h <= MAX_SINGLE_ODD and var_h <= MAX_VARIANCE:
                pick = {**common_data, "team": h_t, "odd": avg_h, "picked": h_t, "home": True}
            elif MIN_SINGLE_ODD <= avg_a <= MAX_SINGLE_ODD and var_a <= MAX_VARIANCE:
                pick = {**common_data, "team": a_t, "odd": avg_a, "picked": a_t, "home": False}
            if pick: all_picks.append(pick)

    # --- WYSYŁKA SINGLE ---
    singles = [p for p in all_picks if p['odd'] >= SINGLE_THRESHOLD]
    for s in singles:
        match_time = (s["date"] + timedelta(hours=1)).strftime('%d.%m %H:%M')
        win = round(STAKE_SINGLE * TAX_RATE * s['odd'], 2)
        msg = (f"🎯 *SINGLE*\n━━━━━━━━━━━━━━━━━━━━\n🏟️ `{s['home_name']} vs {s['away_name']}`\n✅ Typ: `{s['picked']}`\n🏆 {s['league']}\n📅 `{match_time}` | 📈 `{s['odd']:.2f}`\n━━━━━━━━━━━━━━━━━━━━\n💰 Stawka: `{STAKE_SINGLE} PLN` | Wygrana: `{win} PLN`")
        send_msg(msg)
        coupons_db.append({"status": "pending", "stake": STAKE_SINGLE, "win_val": win, "end_time": s["date"].isoformat(), "matches": [{"id": s["id"], "picked": s["picked"], "sport_key": s["key"]}]})
        all_picks = [p for p in all_picks if p['id'] != s['id']]

    # --- WYSYŁKA DOUBLE ---
    all_picks.sort(key=lambda x: (x['home'], x['odd']), reverse=True)
    while len(all_picks) >= 2:
        p1 = all_picks.pop(0)
        p2_idx = next((i for i, x in enumerate(all_picks) if x['league'] != p1['league']), -1)
        if p2_idx == -1: break
        p2 = all_picks.pop(p2_idx)
        t1, t2 = (p1["date"] + timedelta(hours=1)).strftime('%d.%m %H:%M'), (p2["date"] + timedelta(hours=1)).strftime('%d.%m %H:%M')
        ako, win = round(p1['odd'] * p2['odd'], 2), round(STAKE_STANDARD * TAX_RATE * (p1['odd'] * p2['odd']), 2)
        msg = (f"🚀 *DOUBLE (AKO)*\n━━━━━━━━━━━━━━━━━━━━\n1️⃣ `{p1['home_name']} vs {p1['away_name']}`\n   ✅ `{p1['picked']}` | `{p1['odd']:.2f}`\n   🏆 {p1['league']} | 📅 `{t1}`\n\n2️⃣ `{p2['home_name']} vs {p2['away_name']}`\n   ✅ `{p2['picked']}` | `{p2['odd']:.2f}`\n   🏆 {p2['league']} | 📅 `{t2}`\n━━━━━━━━━━━━━━━━━━━━\n📊 AKO: `{ako:.2f}` | 💰 Wygrana: `{win} PLN`")
        send_msg(msg)
        coupons_db.append({"status": "pending", "stake": STAKE_STANDARD, "win_val": win, "end_time": max(p1["date"], p2["date"]).isoformat(), "matches": [{"id": p1["id"], "picked": p1["picked"], "sport_key": p1["key"]}, {"id": p2["id"], "picked": p2["picked"], "sport_key": p2["key"]}]})
    
    save_coupons(coupons_db)
    if now_utc.hour == 8: send_daily_report()
    print("✅ Gotowe.")

if __name__ == "__main__":
    run()
