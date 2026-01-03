import requests
import os
import json
from datetime import datetime, timedelta, timezone

# ================= KONFIGURACJA =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")
KEYS_POOL = [os.getenv(f"ODDS_KEY{i}") for i in ["", "_2", "_3", "_4", "_5"]]
API_KEYS = [k for k in KEYS_POOL if k]

MIN_SINGLE_ODD = 1.55
MAX_SINGLE_ODD = 2.50
TAX_RATE = 0.88
STAKE_SINGLE = 80.0
MAX_VARIANCE = 0.12
MIN_BOOKMAKERS = 4

SPORTS_CONFIG = {
    "soccer_epl": "⚽ EPL", "soccer_spain_la_liga": "⚽ La Liga",
    "soccer_germany_bundesliga": "⚽ Bundesliga", "soccer_italy_serie_a": "⚽ Serie A",
    "soccer_france_ligue_one": "⚽ Ligue 1", "soccer_poland_ekstraklasa": "⚽ Ekstraklasa",
    "soccer_uefa_champions_league": "⚽ LM", "basketball_nba": "🏀 NBA", "icehockey_nhl": "🏒 NHL"
}

COUPONS_FILE = "coupons.json"

# ================= FUNKCJE POMOCNICZE =================

def load_coupons():
    if not os.path.exists(COUPONS_FILE): return []
    try:
        with open(COUPONS_FILE, "r", encoding="utf-8") as f: return json.load(f)
    except: return []

def save_coupons(coupons):
    with open(COUPONS_FILE, "w", encoding="utf-8") as f: 
        json.dump(coupons[-500:], f, indent=4)

def send_msg(text):
    if not T_TOKEN or not T_CHAT: return
    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
    try: 
        requests.post(url, json={"chat_id": T_CHAT, "text": text, "parse_mode": "Markdown"}, timeout=15)
    except: pass

# ================= RAPORTY =================

def send_daily_report():
    coupons = load_coupons()
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    completed = [c for c in coupons if c.get("status") in ["win", "loss"] 
                 and datetime.fromisoformat(c["end_time"]) > yesterday]
    
    if not completed: return

    total_stake = sum(c["stake"] for c in completed)
    total_win = sum(c["win_val"] if c["status"] == "win" else 0 for c in completed)
    profit = total_win - total_stake
    wins = len([c for c in completed if c["status"] == "win"])
    
    msg = (f"📊 *RAPORT DZIENNY*\n━━━━━━━━━━━━━━━\n"
           f"✅ Trafione: `{wins}/{len(completed)}`\n"
           f"💰 Bilans: `{profit:+.2f} PLN` {( '📈' if profit >= 0 else '📉' )}")
    send_msg(msg)

def send_weekly_report():
    coupons = load_coupons()
    last_week = datetime.now(timezone.utc) - timedelta(days=7)
    completed = [c for c in coupons if c.get("status") in ["win", "loss"] 
                 and datetime.fromisoformat(c["end_time"]) > last_week]
    
    if not completed: return

    total_stake = sum(c["stake"] for c in completed)
    total_win = sum(c["win_val"] if c["status"] == "win" else 0 for c in completed)
    profit = total_win - total_stake
    yield_val = (profit / total_stake) * 100 if total_stake > 0 else 0
    wins = len([c for c in completed if c["status"] == "win"])
    
    msg = (f"📅 *PODSUMOWANIE TYGODNIA*\n━━━━━━━━━━━━━━━━━━━━\n"
           f"🎯 Skuteczność: `{ (wins / len(completed)) * 100:.1f}%`\n"
           f"📊 Yield: `{yield_val:+.2f}%` (`{len(completed)}` kuponów)\n"
           f"💰 Zysk/Strata: `{profit:+.2f} PLN` {( '🚀' if profit >= 0 else '📉' )}\n"
           f"━━━━━━━━━━━━━━━━━━━━")
    send_msg(msg)

# ================= ROZLICZANIE (Z NAZWAMI DRUŻYN) =================

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
                            updated = True
                            
                            icon = "✅" if c["status"] == "win" else "❌"
                            res_text = (f"{icon} *KUPON ROZLICZONY*\n"
                                        f"━━━━━━━━━━━━━━━\n"
                                        f"🏟️ `{h_t} {h_s}:{a_s} {a_t}`\n"
                                        f"🎯 Typ: `{m_saved['picked']}`\n"
                                        f"💰 Bilans: `{ (c['win_val'] - c['stake'] if c['status'] == 'win' else -c['stake']):+.2f} PLN`")
                            send_msg(res_text)
                        break
                except: continue
            
    if updated: save_coupons(coupons)

# ================= ANALIZA I RUN =================

def run():
    check_results()
    now_utc = datetime.now(timezone.utc)
    coupons_db = load_coupons()
    sent_ids = [m["id"] for c in coupons_db for m in c["matches"]]
    
    # --- TUTAJ TWOJA PĘTLA ANALIZY I WYSYŁANIA NOWYCH TYPÓW ---
    # (Pamiętaj, aby przy zapisie 'pending' dodawać sport_key do matches)
    # ---------------------------------------------------------

    save_coupons(coupons_db)
    
    # Raporty rano (GitHub Actions o odpowiedniej godzinie)
    if now_utc.hour in [7, 8, 9]:
        send_daily_report()
        if now_utc.weekday() == 0: # 0 = Poniedziałek
            send_weekly_report()

if __name__ == "__main__":
    run()
