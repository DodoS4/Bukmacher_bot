import requests
import os

# Wczytaj zmienne (upewnij się, że są ustawione w systemie)
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS")

def test_telegram():
    print("--- START TESTU TELEGRAMA ---")
    
    if not T_TOKEN:
        print("❌ BŁĄD: Brak T_TOKEN w zmiennych środowiskowych!")
        return

    # 1. Sprawdź czy Token jest poprawny (Metoda getMe)
    print(f"1. Sprawdzanie tokena: {T_TOKEN[:10]}... ")
    url_me = f"https://api.telegram.org/bot{T_TOKEN}/getMe"
    try:
        r_me = requests.get(url_me)
        if r_me.status_code == 200:
            data = r_me.json()
            print(f"   ✅ Token poprawny! Nazwa bota: @{data['result']['username']}")
        else:
            print(f"   ❌ Token nieprawidłowy! Odpowiedź: {r_me.text}")
            return
    except Exception as e:
        print(f"   ❌ Błąd połączenia: {e}")
        return

    # 2. Test wysyłki do głównego kanału (T_CHAT)
    if T_CHAT:
        print(f"2. Próba wysłania wiadomości testowej do T_CHAT ({T_CHAT})...")
        url_msg = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
        payload = {
            "chat_id": T_CHAT,
            "text": "🛠 <b>Test bota</b>\nStatus: <code>Połączenie działa!</code>",
            "parse_mode": "HTML"
        }
        r_msg = requests.post(url_msg, json=payload)
        if r_msg.status_code == 200:
            print("   ✅ Wiadomość wysłana pomyślnie!")
        else:
            print(f"   ❌ Błąd wysyłki! Telegram zwrócił: {r_msg.text}")
            print("   WSKAZÓWKA: Upewnij się, że bot jest administratorem kanału/grupy!")
    else:
        print("2. ⚠️ Pominęto: Brak zdefiniowanego T_CHAT.")

    # 3. Test wysyłki do kanału wyników (T_CHAT_RESULTS)
    if T_CHAT_RESULTS:
        print(f"3. Próba wysłania wiadomości do T_CHAT_RESULTS ({T_CHAT_RESULTS})...")
        payload["chat_id"] = T_CHAT_RESULTS
        r_res = requests.post(url_msg, json=payload)
        if r_res.status_code == 200:
            print("   ✅ Wiadomość wynikowa wysłana!")
        else:
            print(f"   ❌ Błąd wysyłki wyników! Odpowiedź: {r_res.text}")
    
    print("\n--- KONIEC TESTU ---")

if __name__ == "__main__":
    test_telegram()
