import os
import requests
import json

# ================= KONFIGURACJA LIG I EMOJI =================
SPORTS_CONFIG = {
    "basketball_nba": "🏀", 
    "icehockey_nhl": "🏒", 
    "soccer_epl": "⚽",
    "soccer_spain_la_liga": "🇪🇸", 
    "soccer_germany_bundesliga": "🇩🇪",
    "soccer_italy_serie_a": "🇮🇹", 
    "soccer_france_ligue_one": "🇫🇷",
    "soccer_efl_championship": "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
    "soccer_portugal_primeira_liga": "🇵🇹"
}

LEAGUES = list(SPORTS_CONFIG.keys())

API_KEYS = [
    os.getenv("ODDS_KEY"),
    os.getenv("ODDS_KEY_2"),
    os.getenv("ODDS_KEY_3"),
    os.getenv("ODDS_KEY_4"),
    os.getenv("ODDS_KEY_5")
]

TELEGRAM_TOKEN = os.getenv("T_TOKEN")
TELEGRAM_CHAT = os.getenv("T_CHAT")
STAKE = 250 

def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT, "text": message, "parse_mode": "HTML"})
    except: pass

def get_data(league, key):
    url = f"https://api.the-odds-api.com/v4/sports/{league}/odds/"
    params = {
        "apiKey": key,
        "regions": "eu",
        "markets": "h2h",
        "oddsFormat": "decimal"
    }
    response = requests.get(url, params=params)
    if response.status_code == 200:
        return response.json()
    return None

def main():
    active_key_index = 0
    coupons = []

    for league in LEAGUES:
        emoji = SPORTS_CONFIG.get(league, "🏆")
        data = None
        
        while active_key_index < len(API_KEYS):
            if not API_KEYS[active_key_index]: 
                active_key_index += 1
                continue
            data = get_data(league, API_KEYS[active_key_index])
            if data is not None: break
            active_key_index += 1
        
        if not data: continue

        for event in data:
            home_team = event['home_team']
            away_team = event['away_team']
            
            for bookie in event['bookmakers']:
                for market in bookie['markets']:
                    if market['key'] == 'h2h':
                        for outcome in market['outcomes']:
                            odds = outcome['price']
                            # Filtr: Kursy od 1.95 do 3.50 (najlepsze Value)
                            if 1.95 <= odds <= 3.50:
                                msg = f"{emoji} <b>{home_team} - {away_team}</b>\n"
                                msg += f"━━━━━━━━━━━━━━━\n"
                                msg += f"📍 Typ: <b>{outcome['name']}</b>\n"
                                msg += f"📈 Kurs: <b>{odds}</b>\n"
                                msg += f"💰 Stawka: <b>{STAKE} PLN</b>\n"
                                msg += f"━━━━━━━━━━━━━━━"
                                
                                send_telegram(msg)
                                coupons.append({
                                    "id": event['id'], "home": home_team, "away": away_team,
                                    "outcome": outcome['name'], "odds": odds,
                                    "stake": STAKE, "sport": league
                                })

    with open("coupons.json", "w") as f:
        json.dump(coupons, f, indent=4)

if __name__ == "__main__":
    main()
