import os
import requests
import json
from datetime import datetime, timedelta, timezone

# ================= KONFIGURACJA LIG =================
SPORTS_CONFIG = {
    # HOKEJ 🏒
    "icehockey_nhl": "🇺🇸", 
    "icehockey_sweden_hockeyallsvenskan": "🇸🇪",
    "icehockey_finland_liiga": "🇫🇮",
    "icehockey_germany_del": "🇩🇪",
    "icehockey_czech_extraliga": "🇨🇿",
    "icehockey_switzerland_nla": "🇨🇭",
    "icehockey_austria_liga": "🇦🇹",
    "icehockey_denmark_metal_ligaen": "🇩🇰",
    "icehockey_norway_eliteserien": "🇳🇴",
    "icehockey_slovakia_extraliga": "🇸🇰",
    
    # PIŁKA NOŻNA ⚽
    "soccer_epl": "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
    "soccer_germany_bundesliga": "🇩🇪",
    "soccer_italy_serie_a": "🇮🇹", 
    "soccer_spain_la_liga": "🇪🇸",
    "soccer_poland_ekstraklasa": "🇵🇱",
    "soccer_france_ligue_one": "🇫🇷",
    "soccer_portugal_primeira_liga": "🇵🇹",
    "soccer_netherlands_eredivisie": "🇳🇱",
    "soccer_turkey_super_lig": "🇹🇷",
    "soccer_belgium_first_division_a": "🇧🇪",
    "soccer_austria_bundesliga": "🇦🇹",
    "soccer_denmark_superliga": "🇩🇰",
    "soccer_greece_super_league": "🇬🇷",
    "soccer_switzerland_superleague": "🇨🇭",
    "soccer_scotland_premier_league": "🏴󠁧󠁢󠁳󠁣󠁴󠁿",
    "soccer_efl_championship": "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
    
    # KOSZYKÓWKA 🏀
    "basketball_euroleague": "🇪🇺"
}

API_KEYS = [os.getenv(f"ODDS_KEY_{i}" if i > 1 else "ODDS_KEY") for i in range(1, 11)]
API_KEYS = [k for k in API_KEYS if k]

TOKEN = os.getenv("T_TOKEN")
CHAT_ID = os.getenv("T_CHAT")
COUPONS_FILE = "coupons.json"
KEY_STATE_FILE = "key_index.txt"
BASE_STAKE = 350

def send_telegram(message):
    if not TOKEN or not CHAT_ID: return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}, timeout=10)
    except: pass

def main():
    if not API_KEYS: return
    
    idx = 0
    if os.path.exists(KEY_STATE_FILE):
        try:
            with open(KEY_STATE_FILE, "r") as f: idx = int(f.read().strip()) % len(API_KEYS)
        except: pass

    all_coupons = []
    if os.path.exists(COUPONS_FILE):
        try:
            with open(COUPONS_FILE, "r") as f:
                content = f.read().strip()
                if content:
                    all_coupons = json.loads(content)
            if isinstance(all_coupons, str):
                all_coupons = json.loads(all_coupons)
        except: all_coupons = []
    
    if not isinstance(all_coupons, list): all_coupons = []
    sent_ids = {c['id'] for c in all_coupons if isinstance(c, dict) and 'id' in c}
    now = datetime.now(timezone.utc)

    for league, flag in SPORTS_CONFIG.items():
        url = f"https://api.the-odds-api.com/v4/sports/{league}/odds/"
        try:
            resp = requests.get(url, params={"apiKey": API_KEYS[idx], "regions": "eu", "markets": "h2h"}, timeout=15)
            if resp.status_code == 429: 
                idx = (idx + 1) % len(API_KEYS)
                continue
            data = resp.json()
        except: continue

        if not isinstance(data, list): continue

        for event in data:
            if event['id'] in sent_ids: continue
            m_time = datetime.fromisoformat(event['commence_time'].replace("Z", "+00:00"))
            if m_time < now: continue

            prices = {}
            for b in event.get('bookmakers', []):
                for m in b.get('markets', []):
                    if m['key'] == 'h2h':
                        for o in m.get('outcomes', []):
                            prices.setdefault(o['name'], []).append(o['price'])

            best_choice, best_odds, max_val = None, 0, 0
            for name, p_list in prices.items():
                if name.lower() == "draw" or not p_list: continue
                avg_p = sum(p_list) / len(p_list)
                val = max(p_list) / avg_p
                
                if 1.85 <= max(p_list) <= 5.0 and val > 1.03:
                    if val > max_val: max_val, best_odds, best_choice = val, max(p_list), name

            if best_choice:
                clean_name = league.replace("soccer_", "").replace("icehockey_", "").replace("basketball_", "").replace("_", " ").upper()
                icon = "🏒" if "icehockey" in league else ("🏀" if "basketball" in league else "⚽")
                
                msg = (
                    f"{icon} {flag} <b>{clean_name}</b>\n"
                    f"━━━━━━━━━━━━━━━\n"
                    f"🏟 <b>{event['home_team']}</b> vs <b>{event['away_team']}</b>\n"
                    f"⏰ Start: {m_time.strftime('%d.%m | %H:%M')}\n\n"
                    f"✅ Typ: <b>{best_choice}</b>\n"
                    f"📈 Kurs: <b>{best_odds}</b>\n"
                    f"💰 Stawka: <b>{BASE_STAKE} PLN</b>\n"
                    f"📊 Value: <b>+{round((max_val-1)*100, 1)}%</b>\n"
                    f"━━━━━━━━━━━━━━━"
                )
                send_telegram(msg)
                all_coupons.append({
                    "id": event['id'], "sport": league, "home": event['home_team'], 
                    "away": event['away_team'], "outcome": best_choice, 
                    "odds": best_odds, "stake": BASE_STAKE, "time": event['commence_time']
                })
                sent_ids.add(event['id'])

    with open(KEY_STATE_FILE, "w") as f: f.write(str(idx))
    with open(COUPONS_FILE, "w") as f: json.dump(all_coupons, f, indent=4)

if __name__ == "__main__": main()
