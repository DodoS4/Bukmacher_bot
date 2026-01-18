import os
import requests
import json
from datetime import datetime, timedelta, timezone

# ================= KONFIGURACJA =================
SPORTS_CONFIG = {
    "icehockey_nhl": "🏒", 
    "icehockey_sweden_allsvenskan": "🇸🇪", # SHL/Allsvenskan - świetny hokej pod Value
    "icehockey_finland_liiga": "🇫🇮",      # Fińska Liiga - wysoka nieprzewidywalność
    "soccer_spain_la_liga_2": "🇪🇸",      # Segunda Division - królestwo remisów
    "soccer_poland_ekstraklasa": "🇵🇱",    # Ekstraklasa - duża zmienność
    "soccer_epl": "⚽",
    "soccer_spain_la_liga": "🇪🇸", 
    "soccer_germany_bundesliga": "🇩🇪",
    "soccer_italy_serie_a": "🇮🇹", 
    "soccer_france_ligue_one": "🇫🇷",
    "soccer_efl_championship": "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
    "soccer_portugal_primeira_liga": "🇵🇹",
    "basketball_nba": "🏀"
}

API_KEYS = [os.getenv(f"ODDS_KEY{i}") for i in ["", "_2", "_3", "_4", "_5"]]
TELEGRAM_TOKEN = os.getenv("T_TOKEN")
TELEGRAM_CHAT = os.getenv("T_CHAT")
HISTORY_FILE = "history.json"
BASE_STAKE = 250

def get_smart_stake(league_key):
    if not os.path.exists(HISTORY_FILE):
        return BASE_STAKE
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)
        league_profit = sum(m['profit'] for m in history if m.get('sport') == league_key)
        if league_profit <= -700: return 125
        elif league_profit <= -300: return 200
        return BASE_STAKE
    except:
        return BASE_STAKE

def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try: requests.post(url, json={"chat_id": TELEGRAM_CHAT, "text": message, "parse_mode": "HTML"})
    except: pass

def load_existing_data():
    if os.path.exists("coupons.json"):
        with open("coupons.json", "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                now = datetime.now(timezone.utc)
                cutoff = now - timedelta(hours=48)
                return [c for c in data if datetime.fromisoformat(c['time'].replace("Z", "+00:00")) > cutoff]
            except: return []
    return []

def main():
    active_key_index = 0
    all_coupons = load_existing_data()
    already_sent_ids = [c['id'] for c in all_coupons]
    now = datetime.now(timezone.utc)
    max_future = now + timedelta(hours=48)

    for league, emoji in SPORTS_CONFIG.items():
        current_stake = get_smart_stake(league)
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
            if event['id'] in already_sent_ids: continue
            try:
                match_time = datetime.fromisoformat(event['commence_time'].replace("Z", "+00:00"))
                if match_time > max_future or match_time < now: continue 
            except: continue

            market_prices = {} 
            for bookie in event['bookmakers']:
                for market in bookie['markets']:
                    if market['key'] == 'h2h':
                        for outcome in market['outcomes']:
                            name = outcome['name']
                            if name not in market_prices: market_prices[name] = []
                            market_prices[name].append(outcome['price'])

            best_odds = 0
            best_choice = None
            
            # --- LOGIKA HYBRYDOWA: REMIS + ZWYCIĘSTWO ---
            outcomes = list(market_prices.items())
            if "soccer" in league:
                # W piłce najpierw sprawdź remis
                outcomes.sort(key=lambda x: x[0].lower() != "draw")

            for name, prices in outcomes:
                # Blokada remisów dla NHL/NBA i nowych lig hokejowych
                if ("icehockey" in league or "basketball" in league) and name.lower() == "draw":
                    continue

                max_p = max(prices)
                avg_p = sum(prices) / len(prices)
                
                if 1.95 <= max_p <= 4.5: # Zwiększony zakres dla wysokich kursów
                    if max_p > (avg_p * 1.03): 
                        if name.lower() == "draw":
                            best_odds = max_p
                            best_choice = name
                            break # Jeśli znaleziono opłacalny remis, bierzemy go priorytetowo
                        elif max_p > best_odds:
                            best_odds = max_p
                            best_choice = name

            if best_choice:
                date_str = match_time.strftime('%d.%m | %H:%M')
                league_header = league.replace("soccer_", "").replace("_", " ").upper()
                stake_msg = f"<b>{current_stake} PLN</b>"
                if current_stake < BASE_STAKE: stake_msg += " ⚠️ (Zredukowana)"

                msg = f"{emoji} {league_header}\n━━━━━━━━━━━━━━━\n"
                msg += f"🏟 <b>{event['home_team']}</b> vs <b>{event['away_team']}</b>\n"
                msg += f"⏰ Start: {date_str}\n\n✅ Typ: <b>{best_choice}</b>\n"
                msg += f"📈 Kurs: <b>{best_odds}</b>\n💰 Stawka: {stake_msg}\n━━━━━━━━━━━━━━━"

                send_telegram(msg)
                all_coupons.append({
                    "id": event['id'], "home": event['home_team'], "away": event['away_team'],
                    "outcome": best_choice, "odds": best_odds, "stake": current_stake,
                    "sport": league, "time": event['commence_time']
                })
                already_sent_ids.append(event['id'])

    with open("coupons.json", "w", encoding="utf-8") as f:
        json.dump(all_coupons, f, indent=4)

if __name__ == "__main__":
    main()
