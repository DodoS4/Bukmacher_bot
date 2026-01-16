import json
import os
import requests
from datetime import datetime

# --- KONFIGURACJA ---
ODDS_API_KEY = os.getenv("ODDS_KEY")
TELEGRAM_TOKEN = os.getenv("T_TOKEN")
TELEGRAM_CHAT = os.getenv("T_CHAT_ALERTS")
COUPONS_FILE = "coupons.json"

# Lista lig do skanowania
SPORTS = [
    "soccer_epl",                 # Premier League
    "soccer_spain_la_liga",       # La Liga
    "soccer_germany_bundesliga",  # Bundesliga
    "soccer_italy_serie_a",       # Serie A
    "soccer_france_ligue_one",    # Ligue 1
    "basketball_nba",             # NBA
    "icehockey_nhl"               # NHL
]

def send_telegram(message):
    """Wysyła powiadomienie o nowym typie na Telegram"""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT:
        print("Błąd: Brak tokena lub ID czatu Telegram.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={
            "chat_id": TELEGRAM_CHAT, 
            "text": message, 
            "parse_mode": "HTML"
        })
    except Exception as e:
        print(f"Błąd wysyłania do Telegrama: {e}")

def scan_odds():
    """Skanuje kursy i zapisuje nowe okazje"""
    print(f"Rozpoczynam skanowanie: {datetime.now().strftime('%H:%M:%S')}")

    # 1. Załadowanie istniejących kuponów, aby nie dublować ofert
    if not os.path.exists(COUPONS_FILE):
        with open(COUPONS_FILE, "w") as f:
            json.dump([], f)
    
    with open(COUPONS_FILE, "r") as f:
        coupons = json.load(f)
    
    existing_ids = [c['id'] for c in coupons]

    # 2. Iteracja po każdej lidze
    for sport in SPORTS:
        print(f"Sprawdzam ligę: {sport}...")
        url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/?apiKey={ODDS_API_KEY}&regions=eu&markets=h2h"
        
        try:
            response = requests.get(url)
            data = response.json()
            
            if response.status_code != 200:
                print(f"Błąd API ({sport}): {data.get('message', 'Nieznany błąd')}")
                continue

            for match in data:
                match_id = match['id']
                
                # Pomiń, jeśli już mamy ten mecz w bazie
                if match_id in existing_ids:
                    continue
                
                home_team = match['home_team']
                away_team = match['away_team']
                commence_time = match['commence_time']

                # Pobieramy kursy od pierwszego dostępnego bukmachera
                if not match['bookmakers']:
                    continue
                
                outcomes = match['bookmakers'][0]['markets'][0]['outcomes']
                
                for outcome in outcomes:
                    selected_team = outcome['name']
                    price = outcome['price']

                    # --- LOGIKA FILTROWANIA (KURS 1.70 - 2.50) ---
                    if 1.70 <= price <= 2.50:
                        # Tworzymy nowy kupon
                        new_coupon = {
                            "id": match_id,
                            "home": home_team,
                            "away": away_team,
                            "pick": selected_team,
                            "odds": price,      # KLUCZOWE: Zapisujemy kurs dla stats.py
                            "stake": 20.0,      # Stała stawka 20 PLN
                            "sport": sport,
                            "time": commence_time
                        }
                        
                        coupons.append(new_coupon)
                        existing_ids.append(match_id)

                        # Formatuje wiadomość na Telegram
                        msg = (
                            f"🎯 <b>NOWY TYP WYKRYTY</b>\n"
                            f"🏆 Liga: {sport.upper()}\n"
                            f"⚽ Mecz: <b>{home_team} vs {away_team}</b>\n"
                            f"📝 Typ: <b>{selected_team}</b>\n"
                            f"📈 Kurs: <b>{price}</b>\n"
                            f"💰 Stawka: <b>20 PLN</b>"
                        )
                        send_telegram(msg)
                        
                        # Wyślij tylko jeden typ na mecz (np. na faworyta), aby nie spamować
                        break 

        except Exception as e:
            print(f"Wystąpił błąd podczas skanowania {sport}: {e}")

    # 3. Zapisanie zaktualizowanej listy do pliku
    with open(COUPONS_FILE, "w") as f:
        json.dump(coupons, f, indent=4)
    
    print("Skanowanie zakończone. Dane zapisane.")

if __name__ == "__main__":
    scan_odds()
