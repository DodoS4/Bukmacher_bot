import os
import requests
import json
from datetime import datetime

# ================= KONFIGURACJA =================
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

API_KEYS = [os.getenv(f"ODDS_KEY{i}") for i in ["", "_2", "_3", "_4", "_5"]]
TELEGRAM_TOKEN = os.getenv("T_TOKEN")
TELEGRAM_CHAT = os.getenv("T_CHAT")
STAKE = 250

def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": TELEGRAM_CHAT, "text": message, "parse_mode": "HTML"})

def get_data(league, key):
    url = f"https://api.the-odds-api.com/v4/sports/{league}/odds/"
    params = {"apiKey": key, "regions": "eu", "markets": "h2h"}
    try:
        resp = requests.get(url, params=params, timeout=15)
        return resp.json() if resp.status_code == 200 else None
    except: return None

def main():
    active_key_index = 0
    new_coupons = []
    sent_in_session = set() # Blokada duplikatów w jednym skanie

    for league, emoji in SPORTS_CONFIG.items():
        data = None
        while active_key_index < len(API_KEYS):
            data = get_data(league, API_KEYS[active_key_index])
            if data is not None: break
            active_key_index += 1
        
        if not data: continue

        for event in data:
            if event['id'] in sent_in_session: continue
            
            # Szukamy najlepszego kursu w meczu
            best_odds = 0
            best_choice = None
            league_name = league.replace("soccer_", "").replace("_", " ").upper()

            for bookie in event['bookmakers']:
                for market in bookie['markets']:
                    if market['key'] == 'h2h':
                        for outcome in market['outcomes']:
                            # Filtr kursów (możesz dopasować)
                            if 1.90 <= outcome['price'] <= 4.0:
                                if outcome['price'] > best_odds:
                                    best_odds = outcome['price']
                                    best_choice = outcome['name']

            if best_choice:
                # --- TWÓJ ORYGINALNY STYL WIADOMOŚCI ---
                msg = f"🇫🇷 {league_name}\n" # Automatyczna flaga/nazwa
                msg += f"━━━━━━━━━━━━━━━\n"
                msg += f"🏟 <b>{event['home_team']}</b> vs <b>{event['away_team']}</b>\n"
                
                # Formatowanie czasu (opcjonalne)
                try:
                    dt = datetime.fromisoformat(event['commence_time'].replace("Z", "+00:00"))
                    msg += f"⏰ Start: {dt.strftime('%d.%01 | %H:%M')}\n\n"
                except: pass

                msg += f"✅ Typ: <b>{best_choice}</b>\n"
                msg += f"📈 Kurs: <b>{best_odds}</b>\n"
                msg += f"💰 Stawka: <b>{STAKE} PLN</b>\n"
                msg += f"━━━━━━━━━━━━━━━"

                send_telegram(msg)
                sent_in_session.add(event['id'])
                
                new_coupons.append({
                    "id": event['id'], "home": event['home_team'], "away": event['away_team'],
                    "outcome": best_choice, "odds": best_odds, "stake": STAKE, 
                    "sport": league, "time": event['commence_time']
                })

    with open("coupons.json", "w") as f:
        json.dump(new_coupons, f, indent=4)

if __name__ == "__main__":
    main()
