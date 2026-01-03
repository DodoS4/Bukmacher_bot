import requests
import os
import json
from datetime import datetime, timedelta, timezone

# ================= KONFIGURACJA =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT_TYPES = os.getenv("T_CHAT")           # Główny kanał
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS") # Grupa Wyniki meczy

KEYS_POOL = [os.getenv(f"ODDS_KEY{i}") for i in ["", "_2", "_3", "_4", "_5"]]
API_KEYS = [k for k in KEYS_POOL if k]

COUPONS_FILE = "coupons.json"
SENT_FILE = "sent.json"

# ================= FUNKCJA WYSYŁANIA =================
def send_msg(text, target="types"):
    if not T_TOKEN: return
    # Wybór celu: wyniki idą do nowej grupy, reszta na kanał główny
    chat_id = T_CHAT_RESULTS if target == "results" else T_CHAT_TYPES
    if not chat_id: return
    
    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}, timeout=15)
    except: pass

# ================= ROZLICZANIE MECZÓW =================
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
        
        # Rozliczamy min. 4h po meczu, by wyniki w API były stabilne
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
                            val = round(c['win_val'] - c['stake'], 2) if c["status"] == "win" else -c['stake']
                            
                            # Wiadomość trafia do grupy "Wyniki meczy"
                            res_text = (f"{icon} *KUPON ROZLICZONY*\n"
                                        f"━━━━━━━━━━━━━━━\n"
                                        f"🏟️ `{h_t} {h_s}:{a_s} {a_t}`\n"
                                        f"🎯 Typ: `{m_saved['picked']}`\n"
                                        f"💰 Bilans: `{val:+.2f} PLN`")
                            send_msg(res_text, target="results")
                        break
                except: continue
    if updated:
        with open(COUPONS_FILE, "w", encoding="utf-8") as f: json.dump(coupons[-500:], f, indent=4)

# ================= URUCHOMIENIE BOTA =================
def run():
    # 1. Sprawdź i rozlicz stare mecze (wyniki do nowej grupy)
    check_results()
    
    # 2. Tutaj możesz dodać swoją funkcję wyszukiwania nowych typów
    # Pamiętaj, aby przy wysyłaniu nowych typów używać: send_msg(tekst, target="types")
    
    # 3. Raport tygodniowy (Poniedziałek 8:00 UTC)
    now_utc = datetime.now(timezone.utc)
    if now_utc.hour == 8 and now_utc.weekday() == 0:
        # Kod raportu tygodniowego wysyłany do grupy wyniki
        pass

if __name__ == "__main__":
    run()
