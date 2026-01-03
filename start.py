import requests
import os
import json
from datetime import datetime, timedelta, timezone

# ================= KONFIGURACJA ZMIENNYCH =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT_TYPES = os.getenv("T_CHAT")           # Główny kanał na typy
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS") # Grupa na wyniki: -5257529572

# Pobieranie kluczy API (obsługa wielu kluczy dla uniknięcia limitów)
KEYS_POOL = [os.getenv(f"ODDS_KEY{i}") for i in ["", "_2", "_3", "_4", "_5"]]
API_KEYS = [k for k in KEYS_POOL if k]

# Parametry strategii
MIN_ODD = 1.55
MAX_ODD = 2.50
TAX_RATE = 0.88
STAKE = 80.0
COUPONS_FILE = "coupons.json"

# Konfiguracja lig do analizy
SPORTS = {
    "soccer_epl": "⚽ EPL", 
    "soccer_spain_la_liga": "⚽ La Liga",
    "soccer_germany_bundesliga": "⚽ Bundesliga", 
    "soccer_italy_serie_a": "⚽ Serie A",
    "soccer_france_ligue_one": "⚽ Ligue 1", 
    "soccer_poland_ekstraklasa": "⚽ Ekstraklasa",
    "soccer_uefa_champions_league": "⚽ Liga Mistrzów", 
    "basketball_nba": "🏀 NBA", 
    "icehockey_nhl": "🏒 NHL"
}

# ================= FUNKCJE POMOCNICZE =================

def load_coupons():
    if not os.path.exists(COUPONS_FILE): return []
    try:
        with open(COUPONS_FILE, "r", encoding="utf-8") as f: return json.load(f)
    except: return []

def save_coupons(coupons):
    with open(COUPONS_FILE, "w", encoding="utf-8") as f: 
        json.dump(coupons[-500:], f, indent=4)

def send_msg(text, target="types"):
    if not T_TOKEN: return
    chat_id = T_CHAT_RESULTS if target == "results" else T_CHAT_TYPES
    if not chat_id: return
    
    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
    try: 
        requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}, timeout=15)
    except: pass

# ================= ROZLICZANIE WYNIKÓW =================

def check_results():
    coupons = load_coupons()
    updated = False
    now = datetime.now(timezone.utc)
    
    for c in coupons:
        if c.get("status") != "pending": continue
        end_time = datetime.fromisoformat(c["end_time"])
        if now < end_time + timedelta(hours=4): continue

        for m_saved in c["matches"]:
            s_key = m_saved.get("sport_key")
            for key in API_KEYS:
                try:
                    r = requests.get(f"https://api.the-odds-api.com/v4/sports/{s_key}/scores/", 
                                   params={"apiKey": key, "daysFrom": 3}, timeout=15)
                    if r.status_code == 200:
                        scores = r.json()
                        s_data = next((s for s in scores if s["id"] == m_saved["id"] and s.get("completed")), None)
                        if s_data:
                            h_t, a_t = s_data['home_team'], s_data['away_team']
                            sl = s_data.get("scores", [])
                            h_s = int(next(x['score'] for x in sl if x['name'] == h_t))
                            a_s = int(next(x['score'] for x in sl if x['name'] == a_t))
                            
                            winner = h_t if h_s > a_s else (a_t if a_s > h_s else "Remis")
                            c["status"] = "win" if winner == m_saved["picked"] else "loss"
                            c["end_time"] = datetime.now(timezone.utc).isoformat()
                            updated = True
                            
                            icon = "✅" if c["status"] == "win" else "❌"
                            res_val = round(c['win_val'] - c['stake'], 2) if c["status"] == "win" else -c['stake']
                            
                            res_text = (f"{icon} *KUPON ROZLICZONY*\n"
                                        f"━━━━━━━━━━━━━━━\n"
                                        f"🏟️ `{h_t} {h_s}:{a_s} {a_t}`\n"
                                        f"🎯 Typ: `{m_saved['picked']}`\n"
                                        f"💰 Bilans: `{res_val:+.2f} PLN`")
                            send_msg(res_text, target="results")
                        break
                except: continue
            
    if updated: save_coupons(coupons)

# ================= RAPORT TYGODNIOWY =================

def send_weekly_report():
    coupons = load_coupons()
    last_week = datetime.now(timezone.utc) - timedelta(days=7)
    completed = [c for c in coupons if c.get("status") in ["win", "loss"] 
                 and "end_time" in c and datetime.fromisoformat(c["end_time"]) > last_week]
    
    if not completed: return

    total_stake = sum(c["stake"] for c in completed)
    total_win = sum(c["win_val"] if c["status"] == "win" else 0 for c in completed)
    profit = total_win - total_stake
    wins = len([c for c in completed if c["status"] == "win"])
    accuracy = (wins / len(completed)) * 100
    
    msg = (f"📅 *PODSUMOWANIE TYGODNIA*\n━━━━━━━━━━━━━━━━━━━━\n"
           f"✅ Trafione: `{wins}/{len(completed)}` (`{accuracy:.1f}%`)\n"
           f"💰 Zysk/Strata: `{profit:+.2f} PLN` {( '🚀' if profit >= 0 else '📉' )}\n"
           f"━━━━━━━━━━━━━━━━━━━━")
    send_msg(msg, target="results")

# ================= ANALIZA I URUCHOMIENIE =================

def run():
    check_results()
    now_utc = datetime.now(timezone.utc)
    coupons_db = load_coupons()
    sent_ids = [m["id"] for c in coupons_db for m in c["matches"]]

    # Analiza rynków
    for sport_key, league_label in SPORTS.items():
        for key in API_KEYS:
            try:
                r = requests.get(f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/", 
                               params={"apiKey": key, "regions": "eu", "markets": "h2h"}, timeout=15)
                if r.status_code != 200: continue
                events = r.json()
                
                for ev in events:
                    if ev["id"] in sent_ids: continue
                    
                    # Pobieranie kursów
                    bookies = ev.get("bookmakers", [])
                    if len(bookies) < 3: continue
                    
                    # Logika wyboru kursu (uproszczona dla Single)
                    # Tutaj bot szuka Twoich typów 1.55 - 2.50
                    # Jeśli znajdzie, wysyła: send_msg(tekst_kuponu, target="types")
                break
            except: continue

    save_coupons(coupons_db)
    
    # Raport tygodniowy (Poniedziałek rano)
    if now_utc.weekday() == 0 and 7 <= now_utc.hour <= 10:
        send_weekly_report()

if __name__ == "__main__":
    run()
