import requests
import os

# Wklej tutaj swoje dane, aby sprawdzić czy działają (lub upewnij się, że są w env)
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")
ODDS_KEY = os.getenv("ODDS_KEY")

def test_telegram():
    print("--- TEST TELEGRAMA ---")
    if not T_TOKEN or not T_CHAT:
        print("❌ BŁĄD: Brak T_TOKEN lub T_CHAT w zmiennych środowiskowych.")
        return False
    
    url = f"https://api.telegram.org/bot{T_TOKEN}/getMe"
    try:
        r = requests.get(url).json()
        if r.get("ok"):
            print(f"✅ Bot połączony! Nazwa bota: @{r['result']['username']}")
            
            # Próba wysłania wiadomości
            msg_url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
            m = requests.post(msg_url, json={
                "chat_id": T_CHAT,
                "text": "🔔 Test połączenia: Bot działa poprawnie!"
            })
            if m.status_code == 200:
                print(f"✅ Wiadomość testowa wysłana na ID: {T_CHAT}")
                return True
            else:
                print(f"❌ Błąd wysyłania wiadomości: {m.text}")
        else:
            print(f"❌ Błąd Tokena: {r.get('description')}")
    except Exception as e:
        print(f"❌ Błąd krytyczny Telegrama: {e}")
    return False

def test_odds_api():
    print("\n--- TEST ODDS API ---")
    if not ODDS_KEY:
        print("❌ BŁĄD: Brak ODDS_KEY w zmiennych środowiskowych.")
        return
    
    url = f"https://api.the-odds-api.com/v4/sports/?apiKey={ODDS_KEY}"
    try:
        r = requests.get(url)
        if r.status_code == 200:
            remaining = r.headers.get('x-requests-remaining')
            print(f"✅ API działa! Pozostało zapytań: {remaining}")
        else:
            print(f"❌ Błąd API: {r.status_code} - {r.text}")
    except Exception as e:
        print(
