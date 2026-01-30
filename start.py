import os
import json
import requests
from datetime import datetime, timezone

# --- KONFIGURACJA PLIKÓW ---
COUPONS_FILE = "coupons.json"
BANKROLL_FILE = "bankroll.json"
KEY_INDEX_FILE = "key_index.txt"

# Pobieranie kluczy z Sekretów GitHub (obsługa do 10 kluczy)
API_KEYS = [os.getenv(f"ODDS_KEY_{i}") for i in range(1, 11) if os.getenv(f"ODDS_KEY_{i}")]
if not API_KEYS:
    API_KEYS = [os.getenv("ODDS_KEY")]

def get_current_key():
    """Rotacja kluczy API, aby uniknąć limitów."""
    idx = 0
    if os.path.exists(KEY_INDEX_FILE):
        with open(KEY_INDEX_FILE, "r") as f:
            try:
                idx = int(f.read().strip())
            except:
                idx = 0
    
    current_key = API_KEYS[idx % len(API_KEYS)]
    
    # Zapisz indeks dla następnego uruchomienia
    with open(KEY_INDEX_FILE, "w") as f:
        f.write(str((idx + 1) % len(API_KEYS)))
        
    return current_key

def get_stake():
    """Pobiera saldo i liczy stawkę 5% pod Challenge."""
    balance = 100.0
    if os.path.exists(BANKROLL_FILE):
        try:
            with open(BANKROLL_FILE, "r") as f:
                data = json.load(f)
                balance = float(data.get("balance", 100.0))
        except:
            balance = 100.0
    
    stake = round(balance * 0.05, 2)
    return stake, balance

def send_telegram(message):
    token = os.getenv("T_TOKEN")
    chat_id = os.getenv("T_CHAT")
    if token and chat_id:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
        try:
            requests.post(url, json=payload, timeout=10)
        except Exception as e:
            print(f"⚠️ Błąd wysyłki Telegram: {e}")

def get_bets():
    api_key = get_current_key()
    stake, balance = get_stake()
    
    # ROZSZERZONA LISTA SPORTÓW (USA + HOKEJ + EUROPA)
    sports = [
        "icehockey_nhl", "icehockey_sweden_allsvenskan", "icehockey_sweden_shl",
        "icehockey_finland_liiga", "icehockey_germany_del", "basketball_nba",
        "americanfootball_nfl", "baseball_mlb", "basketball_ncaa",
        "soccer_poland_ekstraklasa", "soccer_uefa_champs_league",
        "soccer_england_league_one", "soccer_spain_la_liga",
        "soccer_germany_bundesliga", "soccer_italy_serie_a",
        "soccer_france_ligue_one", "soccer_netherlands_ere_divisie"
    ]
    
    new_coupons = []
    
    print(f"\n{'='*40}")
    print(f"🔍 DEBUG MODE: CHALLENGE 100 PLN")
    print(f"🏦 Bankroll: {balance} PLN | Stawka 5%: {stake} PLN")
    print(f"📈 Zakres kursów: 1.65 - 3.50")
    print(f"{'='*40}\n")

    for sport in sports:
        print(f"📡 Sprawdzam: {sport}...")
        url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
        params = {
            "apiKey": api_key, "regions": "eu", "markets": "h2h", "oddsFormat": "decimal"
        }
        
        try:
            resp = requests.get(url, params=params, timeout=15)
            if resp.status_code != 200:
                print(f"  ❌ Błąd API: {resp.status_code}")
                continue
            
            matches = resp.json()
            for match in matches:
                home = match.get('home_team')
                away = match.get('away_team')
                
                for bookmaker in match.get('bookmakers', []):
                    if bookmaker['key'] in ['unibet', 'pinnacle', 'williamhill', 'betfair_ex']:
                        market = bookmaker['markets'][0]
                        for outcome in market['outcomes']:
                            price = outcome['price']
                            
                            # --- NOWA LOGIKA KURSU DO 3.50 ---
                            if 1.65 <= price <= 3.50:
                                coupon_id = f"{match['id']}_{outcome['name']}"
                                
                                coupon = {
                                    "id": match['id'],
                                    "unique_id": coupon_id,
                                    "sport": sport,
                                    "home": home,
                                    "away": away,
                                    "outcome": outcome['name'],
                                    "odds": price,
                                    "stake": stake,
                                    "time": match['commence_time']
                                }
                                
                                if not any(c.get('id') == match['id'] for c in new_coupons):
                                    new_coupons.append(coupon)
                                    print(f"  ✅ TYP: {home}-{away} | {outcome['name']} @ {price}")
                                    
                                    msg = (
                                        f"🎯 *NOWY TYP (Challenge 5%)*\n"
                                        f"🏟 Liga: {sport.upper()}\n"
                                        f"⚽ Mecz: {home} - {away}\n"
                                        f"✅ Typ: *{outcome['name']}*\n"
                                        f"📈 Kurs: `{price}`\n"
                                        f"💰 Stawka: `{stake} PLN`"
                                    )
                                    send_telegram(msg)
                                    break
                        break 
        except Exception as e:
            print(f"  💥 Błąd {sport}: {e}")

    # --- ZAPIS I SYNCHRONIZACJA ---
    existing_coupons = []
    if os.path.exists(COUPONS_FILE):
        try:
            with open(COUPONS_FILE, "r") as f:
                existing_coupons = json.load(f)
        except: pass
    
    current_ids = [c.get('id') for c in existing_coupons]
    for nc in new_coupons:
        if nc['id'] not in current_ids:
            existing_coupons.append(nc)

    with open(COUPONS_FILE, "w") as f:
        json.dump(existing_coupons, f, indent=4)

    print(f"\n✅ ZAKOŃCZONO: Dodano {len(new_coupons)} nowych typów.")
    print(f"📦 Razem w grze: {len(existing_coupons)}")

if __name__ == "__main__":
    get_bets()
