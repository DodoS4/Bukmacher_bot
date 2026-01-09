import requests
import os
import sys

# Pobieranie zmiennych z systemu (GitHub Secrets / Environment Variables)
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")
ODDS_KEY = os.getenv("ODDS_KEY")

def test_telegram():
    print("=== 1. TEST TELEGRAMA ===")
    if not T_TOKEN or not T_CHAT:
        print("❌ BŁĄD: Brakuje T_TOKEN lub T_CHAT w ustawieniach!")
        return False
    
    # Sprawdzenie bota
    url_me = f"https://api.telegram.org/bot{T_TOKEN}/getMe"
    try:
        r_me = requests.get(url_me, timeout=10).json()
        if not r_me.get("ok"):
            print(f"❌ BŁĄD TOKENA: Telegram nie rozpoznaje tego tokena. ({r_me.get('description')})")
            return False
        
        print(f"✅ Bot rozpoznany jako: @{r_me['result']['username']}")

        # Próba wysłania wiadomości
        url_msg = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
        payload = {
            "chat_id": T_CHAT,
            "text": "🤖 <b>Test połączenia bota</b>\nJeśli to widzisz, Twój bot i ID czatu są poprawne!",
            "parse_mode": "HTML"
        }
        r_msg = requests.post(url_msg, json=payload, timeout=10).json()
        
        if r_msg.get("ok"):
            print("✅ WIADOMOŚĆ WYSŁANA! Sprawdź telefon.")
            return True
        else:
            print(f"❌ BŁĄD WYSYŁKI: Token OK, ale nie można wysłać wiadomości do {T_CHAT}.")
            print(
