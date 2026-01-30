import os
import json
import requests
from datetime import datetime, timezone

# --- KONFIGURACJA ---
COUPONS_FILE = "coupons.json"
BANKROLL_FILE = "bankroll.json"
KEY_INDEX_FILE = "key_index.txt"

# Pobieranie listy kluczy API z sekretów GitHub
API_KEYS = [os.getenv(f"ODDS_KEY_{i}") for i in range(1, 11) if os.getenv(f"ODDS_KEY_{i}")]
if not API_KEYS:
    # Backup, jeśli masz tylko jeden klucz pod główną nazwą
    API_KEYS = [os.getenv("ODDS_KEY")]

def get_current_key():
    """Zwraca aktualny klucz API na podstawie rotacji."""
    idx = 0
    if os.path.exists(KEY_INDEX_FILE):
        with open(KEY_INDEX_FILE, "r") as f:
            try: idx = int(f.read().strip())
            except: idx = 0
    
    # Rotacja: jeśli index wykroczy poza listę, wraca do 0
    if idx >= len(API_KEYS): idx = 0
    
    # Zapisz następny index dla kolejnego uruchomienia
    with open(KEY_INDEX_FILE, "w") as f:
        f.write(str((idx + 1) % len(API_KEYS)))
        
    return API_KEYS[idx]

def get_stake():
    """Oblicza stawkę 5% z aktualnego bankrolla."""
    balance = 100.0
    if os.path.exists(BANKROLL_FILE):
        with open(BANKROLL_FILE, "r") as f:
            data = json.load(f)
            balance = data.get("balance", 100.0)
    
    # Twoja strategia: 5% bankrolla
    stake = balance * 0.05
    return round(stake, 2), balance

def send_telegram(message):
    token = os.getenv("T_TOKEN")
    chat_id = os.getenv("T_CHAT")
    if token and chat_id:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
        requests.post(url, json=payload)

def get_bets():
    api_key = get_current_key()
    stake, current_balance = get_stake()
    
    # Wybieramy sporty (możesz dodać więcej)
    sports = ["soccer_poland_ekstraklasa", "icehockey_nhl", "soccer_spain_la_liga", "soccer_germany_bundesliga"]
    
    new_coupons = []
    
    print(f"🚀 Start sesji. Bankroll: {current_balance} PLN | Stawka (5%): {stake} PLN")

    for sport in sports:
        url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
        params = {
            "apiKey": api_key,
            "regions": "eu",
            "markets": "h2h",
            "oddsFormat": "decimal"
        }
        
        try:
            resp = requests.get(url, params=params)
            if resp.status_code != 200: continue
            
            matches = resp.json()
            for match in matches:
                # Prosta logika AI: szukamy faworyta z kursem 1.50 - 2.20
                for bookmaker in match.get('bookmakers', []):
                    if bookmaker['key'] == 'pinnacle' or bookmaker['key'] == 'unibet': # Główne rynki
                        market = bookmaker['markets'][0]
                        for outcome in market['outcomes']:
                            price = outcome['price']
                            
                            if 1.60 <= price <= 2.10:
                                coupon = {
                                    "id": match['id'],
                                    "sport": sport,
                                    "home": match['home_team'],
                                    "away": match['away_team'],
                                    "outcome": outcome['name'],
                                    "odds": price,
                                    "stake": stake,
                                    "time": match['commence_time']
                                }
                                
                                # Sprawdź czy już nie mamy tego meczu
                                if not any(c['id'] == coupon['id'] for c in new_coupons):
                                    new_coupons.append(coupon)
                                    
                                    msg = (
                                        f"🎯 *NOWY TYP (5% Kuli)*\n"
                                        f"⚽ Mecz: {match['home_team']} - {match['away_team']}\n"
                                        f"✅ Typ: {outcome['name']}\n"
                                        f"📈 Kurs: `{price}`\n"
                                        f"💰 Stawka: `{stake} PLN`"
                                    )
                                    send_telegram(msg)
                                    print(f"✅ Dodano: {match['home_team']} vs {match['away_team']}")
                                    break
        except Exception as e:
            print(f"❌ Błąd przy pobieraniu {sport}: {e}")

    # Zapis do coupons.json (nadpisujemy lub dopisujemy)
    existing_coupons = []
    if os.path.exists(COUPONS_FILE):
        with open(COUPONS_FILE, "r") as f:
            try: existing_coupons = json.load(f)
            except: existing_coupons = []
    
    # Dodaj tylko unikalne ID
    ids = [c['id'] for c in existing_coupons]
    for nc in new_coupons:
        if nc['id'] not in ids:
            existing_coupons.append(nc)

    with open(COUPONS_FILE, "w") as f:
        json.dump(existing_coupons, f, indent=4)

if __name__ == "__main__":
    get_bets()
