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

def load_existing_ids():
    if os.path.exists("coupons.json"):
        with open("coupons.json", "r") as f:
            try:
                data = json.load(f)
                return [c['id'] for c in data]
            except: return []
    return []

def main():
    active_key_index = 0
    # Wczytujemy ID meczów, które już są w bazie, żeby ich NIE wysyłać ponownie
    already_sent_ids = load_existing_ids()
    new_coupons = []
    
    # Lista obecnych kuponów (żeby ich nie skasować przy nowym skanie)
    if os.path.exists("coupons.json"):
        with open("coupons.json", "r") as f:
            try: all_coupons = json.load(f)
            except: all_coupons = []
    else:
        all_coupons = []

    for league, emoji in SPORTS_CONFIG.items():
        data = None
        while active_key_index < len(API_KEYS):
            url = f"https://api.the-odds-api.com/v4/sports/{league}/odds/"
            params = {"apiKey": API_KEYS[active_key_index], "regions": "eu", "markets": "h2h"}
            resp = requests.get(url, params=params)
            if resp.status_code == 200:
                data = resp.json()
                break
            active_key_index += 1
        
        if not data: continue

        for event in data:
            # BLOKADA DUBLOWANIA: Jeśli ID meczu już wysłaliśmy wcześniej - pomiń
            if event['id'] in already_sent_ids:
                continue
            
            best_odds = 0
            best_choice = None
            league_header = league.replace("soccer_", "").replace("_", " ").upper()

            for bookie in event['bookmakers']:
                for market in bookie['markets']:
                    if market['key'] == 'h2h':
                        for outcome in market['outcomes']:
                            if 1.95 <= outcome['price'] <= 4.0:
                                if outcome['price'] > best_odds:
                                    best_odds = outcome['price']
                                    best_choice = outcome['name']

            if best_choice:
                # NAPRAWA DATY: %m zamiast %01
                try:
                    dt = datetime.fromisoformat(event['commence_time'].replace("Z", "+00:00"))
                    date_str = dt.strftime('%d.%m | %H:%M')
                except:
                    date_str = "Brak daty"

                # TWOJA WIADOMOŚĆ
                msg = f"{emoji} {league_header}\n"
                msg += f"━━━━━━━━━━━━━━━\n"
                msg += f"🏟 <b>{event['home_team']}</b> vs <b>{event['away_team']}</b>\n"
                msg += f"⏰ Start: {date_str}\n\n"
                msg += f"✅ Typ: <b>{best_choice}</b>\n"
                msg += f"📈 Kurs: <b>{best_odds}</b>\n"
                msg += f"💰 Stawka: <b>{STAKE} PLN</b>\n"
                msg += f"━━━━━━━━━━━━━━━"

                send_telegram(msg)
                already_sent_ids.append(event['id']) # Dodaj do wysłanych w tej sesji
                
                all_coupons.append({
                    "id": event['id'], "home": event['home_team'], "away": event['away_team'],
                    "outcome": best_choice, "odds": best_odds, "stake": STAKE, 
                    "sport": league, "time": event['commence_time']
                })

    with open("coupons.json", "w") as f:
        json.dump(all_coupons, f, indent=4)

if __name__ == "__main__":
    main()
