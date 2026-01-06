import requests
import json
import os
from datetime import datetime

# ================= KONFIGURACJA TESTOWA =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")           # Kanał TYPY
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS")   # Kanał WYNIKI
API_KEYS = [os.getenv("ODDS_KEY"), os.getenv("ODDS_KEY_2")]

COUPONS_FILE = "coupons.json"
INITIAL_BANKROLL = 100.0
# Ustawiamy ujemny próg, żeby WYMUSIĆ wysłanie czegokolwiek co znajdzie
VALUE_THRESHOLD = -1.0 

# Wybierz te dwie, bo NHL/NBA zazwyczaj mają najwięcej kursów w nocy
LEAGUES = ["icehockey_nhl", "basketball_nba", "soccer_epl"]

def send_msg(text, target="types"):
    chat_id = T_CHAT_RESULTS if target == "results" else T_CHAT
    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    try:
        r = requests.post(url, json=payload, timeout=15)
        print(f"DEBUG: Wysyłanie do Telegrama ({target}) status: {r.status_code}")
        return r.status_code == 200
    except Exception as e:
        print(f"DEBUG: Błąd Telegrama: {e}")
        return False

def run_diagnostic():
    print(f"🚀 --- START DIAGNOSTYKI --- 🚀")
    print(f"Zmienne: T_CHAT={T_CHAT}, T_CHAT_RESULTS={T_CHAT_RESULTS}")
    
    # 1. Usuwamy stary plik kuponów dla czystego testu
    if os.path.exists(COUPONS_FILE):
        os.remove(COUPONS_FILE)
        print("🗑️ Usunięto stary plik coupons.json dla czystego testu.")

    # 2. Testowe wysłanie wiadomości na oba kanały
    print("\n📡 Testuję komunikację z Telegramem...")
    if send_msg("🧪 Test kanału TYPY", target="types"):
        print("✅ Kanał TYPY: OK")
    else:
        print("❌ Kanał TYPY: BŁĄD")

    if send_msg("🧪 Test kanału WYNIKI", target="results"):
        print("✅ Kanał WYNIKI: OK")
    else:
        print("❌ Kanał WYNIKI: BŁĄD")

    # 3. Skanowanie API
    print("\n🔍 Skanuję API w poszukiwaniu meczów...")
    bankroll = INITIAL_BANKROLL
    
    for league in LEAGUES:
        print(f"\n--- Liga: {league} ---")
        for key in API_KEYS:
            if not key:
                print("⚠️ Brak klucza API, pomijam...")
                continue
            
            try:
                url = f"https://api.the-odds-api.com/v4/sports/{league}/odds"
                params = {"apiKey": key, "regions": "eu", "markets": "h2h"}
                r = requests.get(url, params=params, timeout=15)
                
                print(f"Status API: {r.status_code}")
                if r.status_code != 200:
                    print(f"❌ Błąd API: {r.text}")
                    continue
                
                events = r.json()
                print(f"Liczba znalezionych meczów: {len(events)}")
                
                if len(events) > 0:
                    # Próbujemy wysłać pierwszy lepszy mecz
                    ev = events[0]
                    print(f"Próbuję wysłać mecz: {ev['home_team']} vs {ev['away_team']}")
                    
                    if ev.get("bookmakers"):
                        outcomes = ev["bookmakers"][0]["markets"][0]["outcomes"]
                        for out in outcomes:
                            odds = out["price"]
                            edge = 0.10 # Udawany zysk 10%
                            
                            # Tu jest kluczowy moment - czy wejdzie w ten warunek?
                            if edge >= VALUE_THRESHOLD:
                                print(f"✅ Warunek spełniony! Wysyłam typ na {out['name']}...")
                                msg = (f"🧪 <b>TESTOWY TYP</b>\n"
                                       f"🏟️ {ev['home_team']} - {ev['away_team']}\n"
                                       f"✅ Typ: {out['name']} (Kurs: {odds})")
                                send_msg(msg, target="types")
                                break
                    else:
                        print("⚠️ Mecz nie ma jeszcze wystawionych kursów u bukmacherów.")
                
                break # Jeśli klucz zadziałał, idź do następnej ligi
            except Exception as e:
                print(f"❌ Wyjątek podczas pracy z API: {e}")

    print("\n🚀 --- KONIEC DIAGNOSTYKI ---")

if __name__ == "__main__":
    run_diagnostic()
