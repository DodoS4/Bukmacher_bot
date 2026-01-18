import os
import requests
import json
from datetime import datetime, timedelta, timezone

# ================= KONFIGURACJA =================
SPORTS_CONFIG = {
    "icehockey_nhl": "🏒", 
    "icehockey_sweden_allsvenskan": "🇸🇪",
    "icehockey_finland_liiga": "🇫🇮",
    "soccer_spain_la_liga_2": "🇪🇸",
    "soccer_poland_ekstraklasa": "🇵🇱",
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
COUPONS_FILE = "coupons.json"
BASE_STAKE = 250
MAX_ACTIVE_BETS = 55  # Limit aktywnych kuponów (kontroluje obrót)

def get_smart_stake(league_key):
    """Oblicza stawkę i próg Value na podstawie historii ligi."""
    if not os.path.exists(HISTORY_FILE):
        return BASE_STAKE, 1.03 # Domyślnie 3% przewagi
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)
        league_profit = sum(m['profit'] for m in history if m.get('sport') == league_key)
        
        if league_profit <= -700: return 125, 1.07 # Słaba forma: mała stawka, wysokie wymagania
        if league_profit <= -300: return 200, 1.05
        return BASE_STAKE, 1.03
    except:
        return BASE_STAKE, 1.03

def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try: requests.post(url, json={"chat_id": TELEGRAM_CHAT, "text": message, "parse_mode": "HTML"})
    except: pass

def load_existing_data():
    if os.path.exists(COUPONS_FILE):
        with open(COUPONS_FILE, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                now = datetime.now(timezone.utc)
                # Zostawiamy tylko mecze z ostatnich 48h, które jeszcze nie wygasły
                return [c for c in data if datetime.fromisoformat(c['time'].replace("Z", "+00:00")) > (now - timedelta(hours=48))]
            except: return []
    return []

def main():
    print(f"🚀 START BOT: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    active_key_index = 0
    all_coupons = load_existing_data()
    
    if len(all_coupons) >= MAX_ACTIVE_BETS:
        print(f"🛑 LIMIT: Masz już {len(all_coupons)} aktywnych zakładów. Przerywam, by nie generować zbyt dużego obrotu.")
        return

    already_sent_ids = [c['id'] for c in all_coupons]
    now = datetime.now(timezone.utc)
    max_future = now + timedelta(hours=48)

    for league, emoji in SPORTS_CONFIG.items():
        current_stake, value_threshold = get_smart_stake(league)
        print(f"\n📡 SKANOWANIE: {league.upper()} (Stawka: {current_stake}, Próg: {value_threshold})")
        
        data = None
        while active_key_index < len(API_KEYS):
            if not API_KEYS[active_key_index]:
                active_key_index += 1
                continue
            url = f"https://api.the-odds-api.com/v4/sports/{league}/odds/"
            params = {"apiKey": API_KEYS[active_key_index], "regions": "eu", "markets": "h2h"}
            try:
                resp = requests.get(url, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    break
                print(f"⚠️ Klucz {active_key_index} błąd {resp.status_code}. Zmiana...")
                active_key_index += 1
            except:
                active_key_index += 1
        
        if not data: 
            print(f"❌ Brak danych dla {league}")
            continue

        for event in data:
            if event['id'] in already_sent_ids: continue
            
            try:
                match_time = datetime.fromisoformat(event['commence_time'].replace("Z", "+00:00"))
                if match_time > max_future or match_time < now: continue 
            except: continue

            print(f"  🔍 Analiza: {event['home_team']} - {event['away_team']}")

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
            reject_reason = "Brak Value"
            
            outcomes = list(market_prices.items())
            if "soccer" in league:
                outcomes.sort(key=lambda x: x[0].lower() != "draw") # Priorytet dla remisów

            for name, prices in outcomes:
                if ("icehockey" in league or "basketball" in league) and name.lower() == "draw":
                    continue

                max_p = max(prices)
                avg_p = sum(prices) / len(prices)
                
                if 1.95 <= max_p <= 4.5:
                    if max_p > (avg_p * value_threshold):
                        if name.lower() == "draw":
                            best_odds = max_p
                            best_choice = name
                            break 
                        elif max_p > best_odds:
                            best_odds = max_p
                            best_choice = name
                    else:
                        reject_reason = f"Kurs {max_p} zbyt niski względem średniej {avg_p:.2f}"
                else:
                    reject_reason = f"Kurs {max_p} poza limitem (1.95 - 4.5)"

            if best_choice:
                print(f"    ✅ TRAFIONO: {best_choice} @ {best_odds}")
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
                
                # Sprawdzenie limitu po każdym dodaniu meczu
                if len(all_coupons) >= MAX_ACTIVE_BETS:
                    print("🛑 Osiągnięto limit aktywnych zakładów w trakcie skanowania.")
                    break
            else:
                print(f"    ❌ Odrzucono: {reject_reason}")

    with open(COUPONS_FILE, "w", encoding="utf-8") as f:
        json.dump(all_coupons, f, indent=4)
    print(f"\n✅ ZAKOŃCZONO. Aktywne kupony: {len(all_coupons)}")

if __name__ == "__main__":
    main()
