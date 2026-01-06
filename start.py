import requests
import os
import json
from datetime import datetime

# ================= KONFIGURACJA TESTOWA =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS")
API_KEY = os.getenv("ODDS_KEY") # Testujemy na pierwszym kluczu

def send_test_msg(text, target="types"):
    chat_id = T_CHAT_RESULTS if target == "results" else T_CHAT
    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    try:
        r = requests.post(url, json=payload, timeout=10)
        return r.status_code == 200
    except:
        return False

def run_diagnostic():
    print("🧪 ROZPOCZYNAM DIAGNOSTYKĘ SYSTEMU 9.5/10...")
    
    # 1. Test połączenia z Telegramem
    print("- Testowanie Telegrama...")
    if send_test_msg("🛰️ <b>TEST SYSTEMU:</b> Bot nawiązał połączenie!", "results"):
        print("✅ Telegram: OK (Wiadomość wysłana)")
    else:
        print("❌ Telegram: BŁĄD (Sprawdź T_TOKEN i T_CHAT)")

    # 2. Test API Odds (czy klucz działa)
    print("- Testowanie API Odds...")
    try:
        url = f"https://api.the-odds-api.com/v4/sports"
        r = requests.get(url, params={"apiKey": API_KEY})
        if r.status_code == 200:
            print(f"✅ API Odds: OK (Klucz aktywny, pozostało zapytań: {r.headers.get('x-requests-remaining')})")
        else:
            print(f"❌ API Odds: BŁĄD {r.status_code} (Sprawdź klucz API)")
    except:
        print("❌ API Odds: BŁĄD POŁĄCZENIA")

    # 3. Test plików lokalnych
    print("- Testowanie plików...")
    if os.path.exists("coupons.json"):
        print("✅ coupons.json: Znaleziony")
    else:
        print("⚠️ coupons.json: Nie znaleziono (zostanie utworzony przy pierwszym typie)")

    # 4. Przykładowy wygląd raportu (tylko do podglądu w konsoli)
    print("\n📊 SYMULACJA RAPORTU DLA CIEBIE:")
    print("-" * 30)
    print(f"💰 Portfel: 100.0 PLN")
    print(f"🚀 Zysk: 0.0 PLN (0%)")
    print(f"✅ STATUS: Wszystkie ligi aktywne")
    print("-" * 30)

if __name__ == "__main__":
    run_diagnostic()
