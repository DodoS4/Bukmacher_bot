import os
import requests
import json
import time
from datetime import datetime, timedelta, timezone
from stats import generate_stats

# ================= KONFIGURACJA LIG =================
SPORTS_CONFIG = {
    "icehockey_nhl": "🏒", "icehockey_sweden_hockeyallsvenskan": "🇸🇪",
    "icehockey_finland_liiga": "🇫🇮", "icehockey_germany_del": "🇩🇪",
    "icehockey_czech_extraliga": "🇨🇿", "icehockey_switzerland_nla": "🇨🇭",
    "icehockey_austria_liga": "🇦🇹", "icehockey_denmark_metal_ligaen": "🇩🇰",
    "icehockey_norway_eliteserien": "🇳🇴", "icehockey_slovakia_extraliga": "🇸🇰",
    "soccer_epl": "⚽", "soccer_germany_bundesliga": "🇩🇪",
    "soccer_italy_serie_a": "🇮🇹", "soccer_spain_la_liga": "🇪🇸",
    "soccer_poland_ekstraklasa": "🇵🇱", "soccer_france_ligue_one": "🇫🇷",
    "soccer_portugal_primeira_liga": "🇵🇹", "soccer_netherlands_eredivisie": "🇳🇱",
    "soccer_turkey_super_lig": "🇹🇷", "soccer_belgium_first_division_a": "🇧🇪",
    "soccer_austria_bundesliga": "🇦🇹", "soccer_denmark_superliga": "🇩🇰",
    "soccer_greece_super_league": "🇬🇷", "soccer_switzerland_superleague": "🇨🇭",
    "soccer_scotland_premier_league": "🏴", "soccer_efl_championship": "🏴",
    "basketball_euroleague": "🏀", "tennis_atp_australian_open": "🎾",
    "tennis_wta_australian_open": "🎾"
}

# ================= POZOSTAŁA KONFIGURACJA =================
API_KEYS = []
if os.getenv("ODDS_KEY"): API_KEYS.append(os.getenv("ODDS_KEY"))
for i in range(2, 11):
    key = os.getenv(f"ODDS_KEY_{i}")
    if key and len(key) > 10: API_KEYS.append(key)

TELEGRAM_TOKEN = os.getenv("T_TOKEN")
TELEGRAM_CHAT = os.getenv("T_CHAT")
HISTORY_FILE = "history.json"
COUPONS_FILE = "coupons.json"
KEY_STATE_FILE = "key_index.txt"
BASE_STAKE = 350

# ================= FUNKCJE POMOCNICZE =================

def load_existing_data():
    if os.path.exists(COUPONS_FILE):
        try:
            with open(COUPONS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except: return []
    return []

def save_single_coupon(coupon):
    """Zapisuje kupon natychmiastowo, by uniknąć duplikatów w równoległych procesach."""
    data = load_existing_data()
    data.append(coupon)
    with open(COUPONS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

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
    current_multiplier = 1.0
    threshold = 1.03
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
            league_profit = sum(m.get('profit', 0) for m in history if m.get('sport') == league_key)
            if league_profit <= -700:
                current_multiplier, threshold = 0.5, 1.07
            elif league_profit >= 500:
                current_multiplier = 1.3
        except: pass
    
    final_stake = BASE_STAKE * current_multiplier
    if "nhl" in league_key.lower(): final_stake *= 1.2
    return round(final_stake, 2), threshold

def send_telegram(message):
    if not TELEGRAM_TOKEN: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try: requests.post(url, json={"chat_id": TELEGRAM_CHAT, "text": message, "parse_mode": "HTML"}, timeout=10)
    except: pass

# ================= GŁÓWNA LOGIKA =================

def main():
    print(f"🚀 START BOT PRO: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if not API_KEYS: return

    current_key_idx = get_current_key_idx()
    now = datetime.now(timezone.utc)
    max_future = now + timedelta(hours=48)

    for league, flag_emoji in SPORTS_CONFIG.items():
        # ODŚWIEŻANIE LISTY WYSŁANYCH PRZED KAŻDĄ LIGĄ
        all_coupons = load_existing_data()
        already_sent_ids = [c['id'] for c in all_coupons]
        
        current_stake, base_threshold = get_smart_stake(league)
        print(f"📡 SKANOWANIE: {league.upper()}")
        
        data = None
        attempts = 0
        while attempts < len(API_KEYS):
            active_key = API_KEYS[current_key_idx]
            url = f"https://api.the-odds-api.com/v4/sports/{league}/odds/"
            params = {"apiKey": active_key, "regions": "eu", "markets": "h2h"}
            try:
                resp = requests.get(url, params=params, timeout=15)
                if resp.status_code == 200:
                    data = resp.json()
                    break
                current_key_idx = (current_key_idx + 1) % len(API_KEYS)
                attempts += 1
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

            for name, prices in market_prices.items():
                if name.lower() == "draw": continue
                max_p, avg_p = max(prices), sum(prices) / len(prices)
                curr_val = max_p / avg_p
                
                if 1.85 <= max_p <= 5.0 and curr_val > base_threshold:
                    date_str = m_time.strftime('%d.%m | %H:%M')
                    l_header = league.replace("soccer_", "").replace("icehockey_", "").upper()
                    
                    msg = (f"✅ <b>{flag_emoji} {l_header}</b>\n"
                           f"━━━━━━━━━━━━━━━\n"
                           f"🏟 <b>{event['home_team']}</b> vs <b>{event['away_team']}</b>\n"
                           f"⏰ Start: {date_str}\n\n"
                           f"✅ Typ: <b>{name}</b> | Kurs: <b>{max_p}</b>\n"
                           f"💰 Stawka: <b>{current_stake} PLN</b>\n"
                           f"━━━━━━━━━━━━━━━")
                    
                    send_telegram(msg)
                    
                    new_coupon = {
                        "id": event['id'], "home": event['home_team'], "away": event['away_team'],
                        "outcome": name, "odds": max_p, "stake": current_stake,
                        "sport": league, "time": event['commence_time']
                    }
                    save_single_coupon(new_coupon)
                    already_sent_ids.append(event['id'])
                    break 

    save_current_key_idx(current_key_idx)
    print(f"✅ KONIEC SKANOWANIA.")

if __name__ == "__main__":
    main()
