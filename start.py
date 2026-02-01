import os
import requests
import json
import time
from datetime import datetime, timedelta, timezone

# ================= KONFIGURACJA =================
SPORTS_CONFIG = {
    "icehockey_nhl": "🏒", "icehockey_sweden_hockeyallsvenskan": "🇸🇪",
    "icehockey_finland_liiga": "🇫🇮", "icehockey_germany_del": "🇩🇪",
    "icehockey_czech_extraliga": "🇨🇿", "icehockey_switzerland_nla": "🇨🇭",
    "soccer_epl": "⚽", "soccer_germany_bundesliga": "🇩🇪",
    "soccer_italy_serie_a": "🇮🇹", "soccer_spain_la_liga": "🇪🇸",
    "soccer_poland_ekstraklasa": "🇵🇱", "soccer_france_ligue_one": "🇫🇷",
    "soccer_portugal_primeira_liga": "🇵🇹", "soccer_netherlands_eredivisie": "🇳🇱"
}

API_KEYS = []
if os.getenv("ODDS_KEY"): API_KEYS.append(os.getenv("ODDS_KEY"))
for i in range(2, 6):
    k = os.getenv(f"ODDS_KEY_{i}")
    if k: API_KEYS.append(k)

TOKEN = os.getenv("T_TOKEN")
CHAT_ID = os.getenv("T_CHAT")  # Wysyła nowe typy tutaj
COUPONS_FILE = "coupons.json"
HISTORY_FILE = "history.json"
KEY_STATE_FILE = "key_index.txt"
BASE_STAKE = 350

# ================= FUNKCJE =================

def send_telegram(message):
    if not TOKEN or not CHAT_ID: return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}, timeout=10)
    except: pass

def get_smart_stake(league):
    multiplier, threshold = 1.0, 1.03
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                history = json.load(f)
            profit = sum(m.get('profit', 0) for m in history if m.get('sport') == league)
            if profit <= -500: multiplier, threshold = 0.8, 1.05
        except: pass
    return round(BASE_STAKE * multiplier, 2), threshold

def main():
    print(f"🚀 START BOT: {datetime.now().strftime('%H:%M:%S')}")
    if not API_KEYS: return
    
    # Zarządzanie kluczami
    idx = 0
    if os.path.exists(KEY_STATE_FILE):
        try:
            with open(KEY_STATE_FILE, "r") as f: idx = int(f.read().strip()) % len(API_KEYS)
        except: pass

    all_coupons = []
    if os.path.exists(COUPONS_FILE):
        with open(COUPONS_FILE, "r") as f: all_coupons = json.load(f)
    
    sent_ids = {c['id'] for c in all_coupons}
    now = datetime.now(timezone.utc)

    for league, flag in SPORTS_CONFIG.items():
        stake, threshold = get_smart_stake(league)
        url = f"https://api.the-odds-api.com/v4/sports/{league}/odds/"
        
        try:
            resp = requests.get(url, params={"apiKey": API_KEYS[idx], "regions": "eu", "markets": "h2h"}, timeout=15)
            if resp.status_code == 429: 
                idx = (idx + 1) % len(API_KEYS)
                continue
            data = resp.json()
        except: continue

        for event in data:
            if event['id'] in sent_ids: continue
            
            m_time = datetime.fromisoformat(event['commence_time'].replace("Z", "+00:00"))
            if m_time < now: continue

            prices = {}
            for b in event['bookmakers']:
                for m in b['markets']:
                    if m['key'] == 'h2h':
                        for o in m['outcomes']:
                            prices.setdefault(o['name'], []).append(o['price'])

            best_choice, best_odds, max_val = None, 0, 0
            for name, p_list in prices.items():
                if name.lower() == "draw" or not p_list: continue
                avg_p = sum(p_list) / len(p_list)
                val = max(p_list) / avg_p
                
                if 1.85 <= max(p_list) <= 5.0 and val > threshold:
                    if val > max_val: max_val, best_odds, best_choice = val, max(p_list), name

            if best_choice:
                l_name = league.replace("soccer_", "").replace("icehockey_", "").replace("_", " ").upper()
                s_icon = "🏒" if "icehockey" in league else "⚽"
                date_str = m_time.strftime('%d.%m | %H:%M')

                msg = (
                    f"{s_icon} {flag} <b>{l_name}</b>\n"
                    f"━━━━━━━━━━━━━━━\n"
                    f"🏟 <b>{event['home_team']}</b> vs <b>{event['away_team']}</b>\n"
                    f"⏰ Start: {date_str}\n\n"
                    f"✅ Typ: <b>{best_choice}</b>\n"
                    f"📈 Kurs: <b>{best_odds}</b>\n"
                    f"💰 Stawka: <b>{stake} PLN</b>\n"
                    f"📊 Value: <b>+{round((max_val-1)*100, 1)}%</b>\n"
                    f"━━━━━━━━━━━━━━━"
                )
                send_telegram(msg)
                all_coupons.append({"id": event['id'], "sport": league, "home": event['home_team'], 
                                   "away": event['away_team'], "outcome": best_choice, 
                                   "odds": best_odds, "stake": stake, "time": event['commence_time']})
                sent_ids.add(event['id'])

    with open(KEY_STATE_FILE, "w") as f: f.write(str(idx))
    with open(COUPONS_FILE, "w") as f: json.dump(all_coupons, f, indent=4)

if __name__ == "__main__":
    main()
