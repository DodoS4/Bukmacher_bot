import os
import requests

def test_system():
    print("🔍 --- START DIAGNOSTYKI SYSTEMU ---")
    
    # 1. Sprawdzanie zmiennych środowiskowych
    vars_to_check = ["T_TOKEN", "T_CHAT", "ODDS_KEY"]
    found_any = False
    
    for var in vars_to_check:
        value = os.environ.get(var)
        if value:
            # Pokazujemy tylko 3 pierwsze znaki dla bezpieczeństwa
            print(f"✅ Znaleziono {var}: {value[:3]}*** (Długość: {len(value)})")
            found_any = True
        else:
            print(f"❌ BRAK zmiennej: {var}")

    if not found_any:
        print("\n❗ UWAGA: GitHub nie przekazał ŻADNYCH sekretów do Pythona.")
        print("Sprawdź, czy w pliku .yml sekcja 'env:' jest pod krokiem 'run'.")

    # 2. Test połączenia z API Telegrama (jeśli klucze są)
    token = os.environ.get("T_TOKEN")
    chat = os.environ.get("T_CHAT")
    
    if token and chat:
        print("\n📡 Testowanie wysyłki na Telegram...")
        url = f"https://api.telegram.org/bot{token}/getMe"
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                print(f"✅ Token Bot API jest POPRAWNY: {r.json()['result']['username']}")
                
                # Próba wysłania testowej wiadomości
                send_url = f"https://api.telegram.org/bot{token}/sendMessage"
                r_send = requests.post(send_url, json={
                    "chat_id": chat,
                    "text": "🚀 Test połączenia bota Dawida: DZIAŁA!"
                })
                if r_send.status_code == 200:
                    print("✅ WIADOMOŚĆ TESTOWA WYSŁANA!")
                else:
                    print(f"❌ Błąd wysyłki: {r_send.text}")
            else:
                print(f"❌ Token jest NIEPRAWIDŁOWY: {r.text}")
        except Exception as e:
            print(f"❌ Błąd sieciowy Telegrama: {e}")

    print("\n--- KONIEC DIAGNOSTYKI ---")

if __name__ == "__main__":
    test_system()
