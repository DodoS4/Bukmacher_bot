import requests
import os
import json
from datetime import datetime, timedelta, timezone

# ================= KONFIGURACJA ZMIENNYCH =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT_TYPES = os.getenv("T_CHAT")           # Główny kanał na typy
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS") # Grupa na wyniki: -5257529572

KEYS_POOL = [os.getenv(f"ODDS_KEY{i}") for i in ["", "_2", "_3", "_4", "_5"]]
API_KEYS = [k for k in KEYS_POOL if k]

COUPONS_FILE = "coupons.json"

# ================= FUNKCJA WYSYŁANIA =================

def send_msg(text, target="types"):
    if not T_TOKEN:
        print("BŁĄD: Brak T_TOKEN w Secrets!")
        return
    
    chat_id = T_CHAT_RESULTS if target == "results" else T_CHAT_TYPES
    
    if not chat_id:
        print(f"BŁĄD: Brak ID dla celu: {target}")
        return
    
    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    
    try: 
        r = requests.post(url, json=payload, timeout=15)
        if r.status_code == 200:
            print(f"SUKCES: Wiadomość wysłana do {target}")
        else:
            print(f"BŁĄD API: {r.status_code} - {r.text}")
    except Exception as e:
        print(f"BŁĄD POŁĄCZENIA: {e}")

# ================= FUNKCJA TESTOWA =================

def test_connection():
    print("--- ROZPOCZYNAM TEST POŁĄCZENIA ---")
    
    # Test 1: Kanał główny
    test_msg_1 = "🤖 *TEST BOT:* To jest wiadomość testowa wysłana na kanał z **TYPAMI**."
    send_msg(test_msg_1, target="types")
    
    # Test 2: Grupa wyniki
    test_msg_2 = "📊 *TEST BOT:* To jest wiadomość testowa wysłana do grupy z **WYNIKAMI**."
    send_msg(test_msg_2, target="results")
    
    print("--- KONIEC TESTU ---")

# ================= ROZLICZANIE WYNIKÓW (Logika właściwa) =================

def check_results():
    if not os.path.exists(COUPONS_FILE): return
    try:
        with open(COUPONS_FILE, "r", encoding="utf-8") as f: coupons = json.load(f)
    except: return

    updated = False
    now = datetime.now(timezone.utc)
    
    for c in coupons:
        if c.get("status") != "pending": continue
        # Rozliczanie następuje min. 4h po meczu
        end_time = datetime.fromisoformat(c["end_time"])
        if now < end_time + timedelta(hours=4): continue
        
        # Tutaj następuje pobieranie wyników z API...
        # Jeśli mecz znaleziony i zakończony:
        # send_msg(res_text, target="results")
        pass

# ================= URUCHOMIENIE =================

def run():
    # WYWOŁANIE TESTU - po poprawnym teście możesz usunąć tę linię
    test_connection()
    
    # Właściwa praca bota
    check_results()
    
    # Raport tygodniowy (Poniedziałek)
    now_utc = datetime.now(timezone.utc)
    if now_utc.weekday() == 0 and 7 <= now_utc.hour <= 10:
        if os.path.exists(COUPONS_FILE):
            # Tu wywołanie send_weekly_report()
            pass

if __name__ == "__main__":
    run()
