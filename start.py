import os
import requests
import json
from datetime import datetime, timedelta, timezone

# ================= KONFIGURACJA =================
# Zmodyfikowana lista: Dodany hokej, usunięte NBA, EPL pod obserwacją
SPORTS_CONFIG = {
    # --- HOKEJ (Twoja najsilniejsza strona) ---
    "icehockey_nhl": "🏒", 
    "icehockey_sweden_allsvenskan": "🇸🇪",
    "icehockey_sweden_svenska_rinkbandy": "🇸🇪", # SHL (Szwecja 1)
    "icehockey_finland_liiga": "🇫🇮",
    "icehockey_germany_del": "🇩🇪",              # Niemcy
    "icehockey_czech_extraliga": "🇨🇿",          # Czechy
    "icehockey_switzerland_nla": "🇨🇭",          # Szwajcaria

    # --- PIŁKA NOŻNA ---
    "soccer_epl": "⚽",                         # EPL - OBSERWACJA
    "soccer_germany_bundesliga": "🇩🇪",
    "soccer_italy_serie_a": "🇮🇹", 
    "soccer_spain_la_liga": "🇪🇸",
    "soccer_poland_ekstraklasa": "🇵🇱",
    "soccer_france_ligue_one": "🇫🇷",
    "soccer_france_ligue_two": "🇫🇷",
    "soccer_germany_bundesliga_2": "🇩🇪",
    "soccer_italy_serie_b": "🇮🇹",
    "soccer_spain_la_liga_2": "🇪🇸",
    "soccer_portugal_primeira_liga": "🇵🇹",
    "soccer_netherlands_erevidisie": "🇳🇱",
    "soccer_belgium_first_division_a": "🇧🇪",
    "soccer_turkey_super_lig": "🇹🇷",
    "soccer_efl_championship": "🏴󠁧󠁢󠁥󠁮󠁧󠁿",

    # --- KOSZYKÓWKA (NBA wyłączone) ---
    "basketball_euroleague": "🇪🇺"
}

KEYS_RAW = [os.getenv(f"ODDS_KEY{i}") for i in ["", "_2", "_3", "_4", "_5"]]
API_KEYS = [k for k in KEYS_RAW if k and len(k) > 10]

TELEGRAM_TOKEN = os.getenv("T_TOKEN")
TELEGRAM_CHAT = os.getenv("T_CHAT")
HISTORY_FILE = "history.json"
COUPONS_FILE = "coupons.json"
BASE_STAKE = 250

def get_smart_stake(league_key):
    if not os.path.exists(HISTORY_FILE):
        return BASE_STAKE, 1.03
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)
        league_profit = sum(m['profit'] for m in history if m.get('sport') == league_key)
        # Dynamiczne progi dla lig generujących straty
        if league_profit <= -700: return 125, 1.07
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
                # Zatrzymujemy kupony z ostatnich 72h
                return [c for c in data if datetime.fromisoformat(c['time'].replace("Z", "+00:00")) > (now - timedelta(hours=72))]
            except: return []
    return []

def main():
    print(f"🚀 START BOT: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    all_coupons = load_existing_data()
    already_sent_ids = [c['id'] for c in all_coupons]
    now = datetime.now(timezone.utc)
    max_future = now + timedelta(hours=48)

    current_key_idx = 0

    for league, emoji in SPORTS_CONFIG.items():
        if current_key_idx >= len(API_KEYS):
            print("❌ Brak kluczy API.")
            break

        current_stake, base_threshold = get_smart_stake(league)
        print(f"\n📡 SKANOWANIE: {league.upper()}")
        
        data = None
        while current_key_idx < len(API_KEYS):
            url = f"https://api.the-odds-api.com/v4/sports/{league}/odds/"
            params = {"apiKey": API_KEYS[current_key_idx], "regions": "eu", "markets": "h2h"}
            try:
                resp = requests.get(url, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    break
                elif resp.status_code in [401, 429]:
                    current_key_idx += 1
                else: break
            except:
                current_key_idx += 1
        
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

            best_choice = None
            best_odds = 0
            max_value_found = 0

            for name, prices in market_prices.items():
                # --- CAŁKOWITA REZYGNACJA Z REMISÓW ---
                if name.lower() == "draw":
                    continue

                max_p = max(prices)
                avg_p = sum(prices) / len(prices)
                
                # Skalowanie progu bezpieczeństwa względem wysokości kursu
                if max_p < 2.2:
                    req_val = base_threshold
                elif max_p < 3.2:
                    req_val = base_threshold + 0.03
                else:
                    req_val = base_threshold + 0.07

                current_value = max_p / avg_p

                if 1.95 <= max_p <= 4.0 and current_value > req_val:
                    if current_value > max_value_found:
                        max_value_found = current_value
                        best_odds = max_p
                        best_choice = name

            if best_choice:
                date_str = match_time.strftime('%d.%m | %H:%M')
                # Formatowanie nazwy ligi do nagłówka
                league_header = league.replace("soccer_", "").replace("icehockey_", "").replace("_", " ").upper()
                
                msg = (f"{emoji} {league_header}\n━━━━━━━━━━━━━━━\n"
                       f"🏟 <b>{event['home_team']}</b> vs <b>{event['away_team']}</b>\n"
                       f"⏰ Start: {date_str}\n\n"
                       f"✅ Typ: <b>{best_choice}</b>\n"
                       f"📈 Kurs: <b>{best_odds}</b>\n"
                       f"💰 Stawka: <b>{current_stake} PLN</b>\n"
                       f"📊 Value: <b>+{round((max_value_found-1)*100, 1)}%</b>\n━━━━━━━━━━━━━━━")

                send_telegram(msg)
                all_coupons.append({
                    "id": event['id'], "home": event['home_team'], "away": event['away_team'],
                    "outcome": best_choice, "odds": best_odds, "stake": current_stake,
                    "sport": league, "time": event['commence_time']
                })
                already_sent_ids.append(event['id'])

    with open(COUPONS_FILE, "w", encoding="utf-8") as f:
        json.dump(all_coupons, f, indent=4)
    print(f"✅ KONIEC. Aktywne: {len(all_coupons)}")

if __name__ == "__main__":
    main()
