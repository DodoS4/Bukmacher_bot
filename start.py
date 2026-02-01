import os
import requests
import json
import time
from datetime import datetime, timedelta, timezone

# ================= KONFIGURACJA =================
SPORTS_CONFIG = {
    "icehockey_nhl": "🏒", "soccer_epl": "⚽", "soccer_germany_bundesliga": "🇩🇪",
    "soccer_italy_serie_a": "🇮🇹", "soccer_spain_la_liga": "🇪🇸", "soccer_poland_ekstraklasa": "🇵🇱",
    "soccer_france_ligue_one": "🇫🇷", "basketball_euroleague": "🏀"
}

API_KEYS = []
if os.getenv("ODDS_KEY"): API_KEYS.append(os.getenv("ODDS_KEY"))
for i in range(2, 6):
    key = os.getenv(f"ODDS_KEY_{i}")
    if key: API_KEYS.append(key)

TELEGRAM_TOKEN = os.getenv("T_TOKEN")
TELEGRAM_CHAT = os.getenv("T_CHAT")
HISTORY_FILE = "history.json"
COUPONS_FILE = "coupons.json"
KEY_STATE_FILE = "key_index.txt"
BASE_STAKE = 350

def get_current_key_idx():
    if os.path.exists(KEY_STATE_FILE):
        try:
            with open(KEY_STATE_FILE, "r") as f: return int(f.read().strip()) % len(API_KEYS)
        except: return 0
    return 0

def save_current_key_idx(idx):
    with open(KEY_STATE_FILE, "w") as f: f.write(str(idx))

def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT:
        print("❌ Telegram: Brak konfiguracji (Token/ChatID)!")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try: 
        resp = requests.post(url, json={"chat_id": TELEGRAM_CHAT, "text": message, "parse_mode": "HTML"}, timeout=10)
        if resp.status_code != 200:
            print(f"❌ Telegram Error {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"❌ Błąd sieciowy Telegram: {e}")

def get_smart_stake(league_key):
    multiplier, threshold = 1.0, 1.03
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
            profit = sum(m.get('profit', 0) for m in history if m.get('sport') == league_key)
            if profit <= -500: multiplier, threshold = 0.7, 1.06
            elif profit >= 500: multiplier = 1.2
        except: pass
    return round(BASE_STAKE * multiplier, 2), threshold

def main():
    print(f"🚀 START: {datetime.now().strftime('%H:%M:%S')}")
    if not API_KEYS: return print("❌ Brak kluczy API!")
    
    current_key_idx = get_current_key_idx()
    all_coupons = []
    if os.path.exists(COUPONS_FILE):
        with open(COUPONS_FILE, "r") as f: all_coupons = json.load(f)
    
    sent_ids = {c['id'] for c in all_coupons}
    now = datetime.now(timezone.utc)

    for league, emoji in SPORTS_CONFIG.items():
        stake, threshold = get_smart_stake(league)
        active_key = API_KEYS[current_key_idx]
        url = f"https://api.the-odds-api.com/v4/sports/{league}/odds/"
        
        try:
            resp = requests.get(url, params={"apiKey": active_key, "regions": "eu", "markets": "h2h"}, timeout=15)
            if resp.status_code == 429:
                current_key_idx = (current_key_idx + 1) % len(API_KEYS)
                continue
            data = resp.json()
        except: continue

        for event in data:
            if event['id'] in sent_ids: continue
            
            prices = {}
            for b in event['bookmakers']:
                for m in b['markets']:
                    if m['key'] == 'h2h':
                        for o in m['outcomes']:
                            prices.setdefault(o['name'], []).append(o['price'])

            best_choice, best_odds, max_val = None, 0, 0
            for name, p_list in prices.items():
                if not p_list or name.lower() == "draw": continue
                avg_p = sum(p_list) / len(p_list)
                val = max(p_list) / avg_p
                if 1.80 <= max(p_list) <= 5.0 and val > threshold:
                    if val > max_val: max_val, best_odds, best_choice = val, max(p_list), name

            if best_choice:
                msg = (f"{emoji} <b>{league.upper()}</b>\n"
                       f"🏟 {event['home_team']} vs {event['away_team']}\n"
                       f"✅ Typ: <b>{best_choice}</b> | Kurs: <b>{best_odds}</b>\n"
                       f"💰 Stawka: <b>{stake} PLN</b> (Value: +{round((max_val-1)*100, 1)}%)")
                send_telegram(msg)
                all_coupons.append({"id": event['id'], "sport": league, "home": event['home_team'], 
                                   "away": event['away_team'], "outcome": best_choice, 
                                   "odds": best_odds, "stake": stake, "time": event['commence_time']})
                sent_ids.add(event['id'])

    save_current_key_idx(current_key_idx)
    with open(COUPONS_FILE, "w") as f: json.dump(all_coupons, f, indent=4)

if __name__ == "__main__":
    main()
