import os
import requests
import json
import time
from datetime import datetime, timedelta, timezone

# ================= KONFIGURACJA LIG =================
SPORTS_CONFIG = {
    # --- HOKEJ ---
    "icehockey_nhl": "🏒", 
    "icehockey_sweden_allsvenskan": "🇸🇪",
    "icehockey_finland_liiga": "🇫🇮",
    "icehockey_germany_del": "🇩🇪",
    "icehockey_czech_extraliga": "🇨🇿",
    "icehockey_switzerland_nla": "🇨🇭",
    "icehockey_austria_liga": "🇦🇹",
    # --- PIŁKA NOŻNA ---
    "soccer_epl": "⚽",
    "soccer_germany_bundesliga": "🇩🇪",
    "soccer_italy_serie_a": "🇮🇹", 
    "soccer_spain_la_liga": "🇪🇸",
    "soccer_poland_ekstraklasa": "🇵🇱",
    "soccer_france_ligue_one": "🇫🇷",
    "soccer_portugal_primeira_liga": "🇵🇹",
    "soccer_netherlands_erevidisie": "🇳🇱",
    "soccer_turkey_super_lig": "🇹🇷",
    "soccer_belgium_first_division_a": "🇧🇪"
}

# ================= OBSŁUGA API KEYS =================
API_KEYS = []
if os.getenv("ODDS_KEY"): API_KEYS.append(os.getenv("ODDS_KEY"))
for i in range(2, 11):
    key = os.getenv(f"ODDS_KEY_{i}")
    if key and len(key) > 10:
        API_KEYS.append(key)

TELEGRAM_TOKEN = os.getenv("T_TOKEN")
TELEGRAM_CHAT = os.getenv("T_CHAT")
HISTORY_FILE = "history.json"
COUPONS_FILE = "coupons.json"
BANKROLL_FILE = "bankroll.json"
KEY_STATE_FILE = "key_index.txt"
BASE_STAKE = 250

def get_current_key_idx():
    if os.path.exists(KEY_STATE_FILE):
        try:
            with open(KEY_STATE_FILE, "r") as f:
                return int(f.read().strip()) % len(API_KEYS)
        except: return 0
    return 0

def save_current_key_idx(idx):
    with open(KEY_STATE_FILE, "w") as f:
        f.write(str(idx))

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
    try: requests.post(url, json={"chat_id": TELEGRAM_CHAT, "text": message, "parse_mode": "HTML"}, timeout=10)
    except: pass

def load_existing_data():
    if os.path.exists(COUPONS_FILE):
        with open(COUPONS_FILE, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                now = datetime.now(timezone.utc)
                return [c for c in data if datetime.fromisoformat(c['time'].replace("Z", "+00:00")) > (now - timedelta(hours=72))]
            except: return []
    return []

def main():
    print(f"🚀 START BOT: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # --- BEZPIECZNIK BANKROLLA ---
    if os.path.exists(BANKROLL_FILE):
        try:
            with open(BANKROLL_FILE, "r") as f:
                br = json.load(f).get("bankroll", 0)
                if br < 150:
                    print(f"🛑 STOP: Bankroll ({br} PLN) jest zbyt niski na kolejną stawkę.")
                    return
        except: pass

    if not API_KEYS:
        print("❌ Błąd: Brak kluczy API!")
        return

    current_key_idx = get_current_key_idx()
    all_coupons = load_existing_data()
    already_sent_ids = [c['id'] for c in all_coupons]
    now = datetime.now(timezone.utc)
    max_future = now + timedelta(hours=48)

    for league, flag_emoji in SPORTS_CONFIG.items():
        current_stake, base_threshold = get_smart_stake(league)
        print(f"📡 SKANOWANIE: {league.upper()}")
        
        data = None
        attempts = 0
        
        while attempts < len(API_KEYS):
            active_key = API_KEYS[current_key_idx]
            url = f"https://api.the-odds-api.com/v4/sports/{league}/odds/"
            params = {"apiKey": active_key, "regions": "eu", "markets": "h2h"}
            
            try:
                # DODANY TIMEOUT 20s
                resp = requests.get(url, params=params, timeout=20)
                if resp.status_code == 200:
                    data = resp.json()
                    break
                elif resp.status_code in [401, 429]:
                    print(f"  ⚠️ Klucz {current_key_idx + 1} limit. Przełączam...")
                    current_key_idx = (current_key_idx + 1) % len(API_KEYS)
                    save_current_key_idx(current_key_idx) # Zapis natychmiastowy
                    attempts += 1
                else:
                    break
            except:
                current_key_idx = (current_key_idx + 1) % len(API_KEYS)
                attempts += 1

        if not data: continue

        for event in data:
            if event['id'] in already_sent_ids: continue
            try:
                m_time = datetime.fromisoformat(event['commence_time'].replace("Z", "+00:00"))
                if m_time > max_future or m_time < now: continue 
            except: continue

            market_prices = {} 
            for bookie in event['bookmakers']:
                for market in bookie['markets']:
                    if market['key'] == 'h2h':
                        for out in market['outcomes']:
                            if out['name'] not in market_prices: market_prices[out['name']] = []
                            market_prices[out['name']].append(out['price'])

            best_choice, best_odds, max_val = None, 0, 0

            for name, prices in market_prices.items():
                if name.lower() == "draw": continue
                if len(prices) < 3: continue # Wymagamy min. 3 bukmacherów do średniej
                
                max_p, avg_p = max(prices), sum(prices) / len(prices)
                
                req_val = base_threshold
                if max_p >= 2.2: req_val += 0.03
                if max_p >= 3.2: req_val += 0.04
                
                curr_val = max_p / avg_p
                if 1.90 <= max_p <= 4.5 and curr_val > req_val:
                    if curr_val > max_val:
                        max_val, best_odds, best_choice = curr_val, max_p, name

            if best_choice:
                date_str = m_time.strftime('%d.%m | %H:%M')
                l_header = league.replace("soccer_", "").replace("icehockey_", "").upper().replace("_", " ")
                s_icon = "🏒" if "icehockey" in league else "⚽"
                
                msg = (f"{s_icon} {flag_emoji} <b>{l_header}</b>\n"
                       f"━━━━━━━━━━━━━━━\n"
                       f"🏟 <b>{event['home_team']}</b> vs <b>{event['away_team']}</b>\n"
                       f"⏰ Start: {date_str}\n\n"
                       f"✅ Typ: <b>{best_choice}</b>\n"
                       f"📈 Kurs: <b>{best_odds}</b>\n"
                       f"💰 Stawka: <b>{current_stake} PLN</b>\n"
                       f"📊 Value: <b>+{round((max_val-1)*100, 1)}%</b>\n"
                       f"━━━━━━━━━━━━━━━")

                send_telegram(msg)
                all_coupons.append({
                    "id": event['id'], "home": event['home_team'], "away": event['away_team'],
                    "outcome": best_choice, "odds": best_odds, "stake": current_stake,
                    "sport": league, "time": event['commence_time']
                })
                already_sent_ids.append(event['id'])

    save_current_key_idx(current_key_idx)
    with open(COUPONS_FILE, "w", encoding="utf-8") as f:
        json.dump(all_coupons, f, indent=4)
    print(f"✅ KONIEC. Aktywne kupony: {len(all_coupons)}")

if __name__ == "__main__":
    main()
