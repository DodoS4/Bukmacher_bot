import os
import requests
import json
from datetime import datetime, timedelta, timezone

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
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT, "text": message, "parse_mode": "HTML"})
    except: pass

def load_existing_data():
    """Zarządzanie pamięcią podręczną wysłanych kuponów."""
    if os.path.exists("coupons.json"):
        with open("coupons.json", "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                now = datetime.now(timezone.utc)
                cutoff = now - timedelta(hours=48)
                # Czyścimy tylko to, co już się odbyło
                valid = [c for c in data if datetime.fromisoformat(c['time'].replace("Z", "+00:00")) > cutoff]
                return valid
            except: return []
    return []

def main():
    active_key_index = 0
    all_coupons = load_existing_data()
    already_sent_ids = [c['id'] for c in all_coupons]
    
    now = datetime.now(timezone.utc)
    max_future = now + timedelta(hours=48)

    for league, emoji in SPORTS_CONFIG.items():
        data = None
        while active_key_index < len(API_KEYS):
            if not API_KEYS[active_key_index]:
                active_key_index += 1
                continue
            url = f"https://api.the-odds-api.com/v4/sports/{league}/odds/"
            params = {"apiKey": API_KEYS[active_key_index], "regions": "eu", "markets": "h2h"}
            resp = requests.get(url, params=params)
            if resp.status_code == 200:
                data = resp.json()
                break
            active_key_index += 1
        
        if not data: continue

        for event in data:
            if event['id'] in already_sent_ids:
                continue
            
            try:
                match_time = datetime.fromisoformat(event['commence_time'].replace("Z", "+00:00"))
                if match_time > max_future or match_time < now:
                    continue 
            except: continue

            # --- INTELIGENTNY WYBÓR KURSU (VALUE HUNTING) ---
            best_odds = 0
            best_choice = None
            
            # 1. Agregujemy kursy od wszystkich bukmacherów dla tego meczu
            market_prices = {} 

            for bookie in event['bookmakers']:
                for market in bookie['markets']:
                    if market['key'] == 'h2h':
                        for outcome in market['outcomes']:
                            name = outcome['name']
                            price = outcome['price']
                            if name not in market_prices:
                                market_prices[name] = []
                            market_prices[name].append(price)

            # 2. Wybieramy najlepszą opcję na podstawie matematycznego odchylenia
            for name, prices in market_prices.items():
                # Blokada remisów dla USA (NBA/NHL)
                if league in ["icehockey_nhl", "basketball_nba"] and name.lower() == "draw":
                    continue

                max_p = max(prices)
                avg_p = sum(prices) / len(prices)
                
                # Warunki:
                # - Kurs w Twoim przedziale 1.95 - 4.0
                # - Kurs musi być o min. 3% wyższy od średniej rynkowej (Inteligentne Value)
                if 1.95 <= max_p <= 4.0:
                    if max_p > (avg_p * 1.03): 
                        if max_p > best_odds:
                            best_odds = max_p
                            best_choice = name

            if best_choice:
                date_str = match_time.strftime('%d.%m | %H:%M')
                league_header = league.replace("soccer_", "").replace("_", " ").upper()

                msg = f"{emoji} {league_header}\n"
                msg += f"━━━━━━━━━━━━━━━\n"
                msg += f"🏟 <b>{event['home_team']}</b> vs <b>{event['away_team']}</b>\n"
                msg += f"⏰ Start: {date_str}\n\n"
                msg += f"✅ Typ: <b>{best_choice}</b>\n"
                msg += f"📈 Kurs: <b>{best_odds}</b>\n"
                msg += f"💰 Stawka: <b>{STAKE} PLN</b>\n"
                msg += f"━━━━━━━━━━━━━━━"

                send_telegram(msg)
                
                all_coupons.append({
                    "id": event['id'], "home": event['home_team'], "away": event['away_team'],
                    "outcome": best_choice, "odds": best_odds, "stake": STAKE, 
                    "sport": league, "time": event['commence_time']
                })
                already_sent_ids.append(event['id'])

    with open("coupons.json", "w", encoding="utf-8") as f:
        json.dump(all_coupons, f, indent=4)

if __name__ == "__main__":
    main()
