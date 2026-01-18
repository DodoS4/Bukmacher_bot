import os
import requests
import json
from datetime import datetime, timedelta, timezone

# ================= KONFIGURACJA =================
# Upewnij się, że nazwy lig są zgodne z dokumentacją The-Odds-API
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

# Pobieranie kluczy z GitHub Secrets
KEYS_RAW = [os.getenv(f"ODDS_KEY{i}") for i in ["", "_2", "_3", "_4", "_5"]]
API_KEYS = [k for k in KEYS_RAW if k and len(k) > 10] # Filtrujemy tylko poprawne klucze

TELEGRAM_TOKEN = os.getenv("T_TOKEN")
TELEGRAM_CHAT = os.getenv("T_CHAT")
HISTORY_FILE = "history.json"
COUPONS_FILE = "coupons.json"
BASE_STAKE = 250
MAX_ACTIVE_BETS = 30 # Zwiększyłem do 30 zgodnie z Twoją potrzebą

def get_smart_stake(league_key):
    if not os.path.exists(HISTORY_FILE):
        return BASE_STAKE, 1.03
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)
        league_profit = sum(m['profit'] for m in history if m.get('sport') == league_key)
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
                # Czyścimy tylko bardzo stare wpisy (starsze niż 72h)
                return [c for c in data if datetime.fromisoformat(c['time'].replace("Z", "+00:00")) > (now - timedelta(hours=72))]
            except: return []
    return []

def main():
    print(f"🚀 START BOT: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    all_coupons = load_existing_data()
    
    if len(all_coupons) >= MAX_ACTIVE_BETS:
        print(f"🛑 LIMIT: Masz już {len(all_coupons)} aktywnych zakładów. Czekam na rozliczenie.")
        return

    already_sent_ids = [c['id'] for c in all_coupons]
    now = datetime.now(timezone.utc)
    max_future = now + timedelta(hours=48)

    # Globalny licznik kluczy (jeśli klucz padnie, przechodzimy na następny dla wszystkich lig)
    current_key_idx = 0

    for league, emoji in SPORTS_CONFIG.items():
        if current_key_idx >= len(API_KEYS):
            print("❌ Wszystkie klucze API zostały wykorzystane lub są błędne.")
            break

        current_stake, value_threshold = get_smart_stake(league)
        print(f"\n📡 SKANOWANIE: {league.upper()} (Stawka: {current_stake}, Próg: {value_threshold})")
        
        data = None
        # Próbujemy pobrać dane, w razie błędu 401/429 zmieniamy klucz na stałe
        while current_key_idx < len(API_KEYS):
            url = f"https://api.the-odds-api.com/v4/sports/{league}/odds/"
            params = {"apiKey": API_KEYS[current_key_idx], "regions": "eu", "markets": "h2h"}
            
            try:
                resp = requests.get(url, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    break
                elif resp.status_code in [401, 429]:
                    print(f"⚠️ Klucz {current_key_idx} (Błąd {resp.status_code}). Przełączam na następny...")
                    current_key_idx += 1
                elif resp.status_code == 404:
                    print(f"ℹ️ Liga {league} niedostępna w API (404).")
                    break
                else:
                    print(f"❓ Inny błąd {resp.status_code} dla {league}")
                    break
            except Exception as e:
                print(f"💥 Błąd połączenia: {e}")
                current_key_idx += 1
        
        if not data: 
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
                outcomes.sort(key=lambda x: x[0].lower() != "draw")

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
                        reject_reason = f"Kurs {max_p} vs avg {avg_p:.2f} (Value < {value_threshold})"
                else:
                    reject_reason = f"Kurs {max_p} poza zakresem"

            if best_choice:
                print(f"    ✅ TRAFIONO: {best_choice} @ {best_odds}")
                date_str = match_time.strftime('%d.%m | %H:%M')
                league_header = league.replace("soccer_", "").replace("_", " ").upper()
                stake_msg = f"<b>{current_stake} PLN</b>"

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
                
                if len(all_coupons) >= MAX_ACTIVE_BETS:
                    print("🛑 Osiągnięto limit w trakcie pracy.")
                    break
            else:
                print(f"    ❌ Odrzucono: {reject_reason}")

    with open(COUPONS_FILE, "w", encoding="utf-8") as f:
        json.dump(all_coupons, f, indent=4)
    print(f"\n✅ KONIEC. Aktywne: {len(all_coupons)}")

if __name__ == "__main__":
    main()
