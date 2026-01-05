import requests
import os
import json
from datetime import datetime, timedelta, timezone

# ================= KONFIGURACJA =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT_TYPES = os.getenv("T_CHAT")           # Główny kanał
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS") # Grupa Wyniki

KEYS_POOL = [os.getenv(f"ODDS_KEY{i}") for i in ["", "_2", "_3", "_4", "_5"]]
API_KEYS = [k for k in KEYS_POOL if k]

COUPONS_FILE = "coupons.json"
SENT_FILE = "sent.json"

# ================= WYSYŁKA =================
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
    if not os.path.exists(COUPONS_FILE): return
    try:
        with open(COUPONS_FILE, "r", encoding="utf-8") as f: coupons = json.load(f)
    except: return

    updated = False
    now = datetime.now(timezone.utc)
    
    for c in coupons:
        if c.get("status") != "pending": continue
        end_time = datetime.fromisoformat(c["end_time"])
        
        # Sprawdzamy wynik 4h po meczu
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
                            profit = round(c['win_val'] - c['stake'], 2) if c["status"] == "win" else -c['stake']
                            
                            # Wysyłka do grupy WYNIKI
                            res_text = (f"{icon} *KUPON ROZLICZONY*\n"
                                        f"━━━━━━━━━━━━━━━\n"
                                        f"🏟️ `{h_t} {h_s}:{a_s} {a_t}`\n"
                                        f"🎯 Twój typ: `{m_saved['picked']}`\n"
                                        f"💰 Bilans: `{profit:+.2f} PLN`")
                            send_msg(res_text, target="results")
                        break
                except: continue
    if updated:
        with open(COUPONS_FILE, "w", encoding="utf-8") as f: json.dump(coupons[-500:], f, indent=4)

# ================= RAPORT TYGODNIOWY =================
def send_weekly_report():
    if not os.path.exists(COUPONS_FILE): return
    with open(COUPONS_FILE, "r", encoding="utf-8") as f: coupons = json.load(f)
    
    last_week = datetime.now(timezone.utc) - timedelta(days=7)
    completed = [c for c in coupons if c.get("status") in ["win", "loss"] 
                 and datetime.fromisoformat(c["end_time"]) > last_week]
    
    if not completed: return
    profit = sum((c["win_val"] - c["stake"]) if c["status"] == "win" else -c["stake"] for c in completed)
    wins = len([c for c in completed if c["status"] == "win"])
    
    msg = (f"📅 *PODSUMOWANIE TYGODNIA*\n━━━━━━━━━━━━━━━━━━━━\n"
           f"✅ Trafione: `{wins}/{len(completed)}`\n"
           f"💰 Zysk/Strata: `{profit:+.2f} PLN` {( '🚀' if profit >= 0 else '📉' )}\n"
           f"━━━━━━━━━━━━━━━━━━━━")
    send_msg(msg, target="results")

# ================= START =================
def run():
    # 1. Rozlicz stare mecze i wyślij do grupy 'Wyniki'
    check_results()
    
    # 2. Tutaj bot będzie wykonywał Twoją analizę kursów i wysyłał typy na kanał główny
    # (Tu wklej swoją pętlę szukającą meczów)
    
    # 3. Raport tygodniowy (Poniedziałek)
    now_utc = datetime.now(timezone.utc)
    if now_utc.hour == 8 and now_utc.weekday() == 0:
        send_weekly_report()

if __name__ == "__main__":
    run()
