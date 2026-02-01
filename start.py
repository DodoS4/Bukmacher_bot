import os
import requests
import json
import time
from datetime import datetime, timedelta, timezone

# ================= KONFIGURACJA LIG (EMOJI + FLAGI) =================
SPORTS_CONFIG = {
    "icehockey_nhl": "🏒", 
    "icehockey_sweden_hockeyallsvenskan": "🇸🇪",
    "icehockey_finland_liiga": "🇫🇮",
    "icehockey_germany_del": "🇩🇪",
    "icehockey_czech_extraliga": "🇨🇿",
    "icehockey_switzerland_nla": "🇨🇭",
    "icehockey_austria_liga": "🇦🇹",
    "icehockey_denmark_metal_ligaen": "🇩🇰",
    "icehockey_norway_eliteserien": "🇳🇴",
    "icehockey_slovakia_extraliga": "🇸🇰",
    "soccer_epl": "⚽",
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
    "soccer_scotland_premier_league": "🏴",
    "soccer_efl_championship": "🏴",
    "basketball_euroleague": "🏀"
}

# ================= KONFIGURACJA SYSTEMOWA =================
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

def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT:
        print("❌ Błąd konfiguracji Telegrama.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try: 
        resp = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT, 
            "text": message, 
            "parse_mode": "HTML"
        }, timeout=15)
        if resp.status_code != 200:
            print(f"❌ Telegram Error: {resp.text}")
    except Exception as e:
        print(f"❌ Błąd sieciowy (Telegram): {e}")

def get_smart_stake(league_key):
    multiplier, threshold = 1.0, 1.03
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
            l_profit = sum(m.get('profit', 0) for m in history if m.get('sport') == league_key)
            if l_profit <= -700: multiplier, threshold = 0.5, 1.07
            elif l_profit <= -300: multiplier, threshold = 0.8, 1.05
            elif l_profit >= 500: multiplier = 1.3
        except: pass
    
    final_stake = BASE_STAKE * multiplier
    if "nhl" in league_key.lower(): final_stake *= 1.1
    return round(final_stake, 2), threshold

# ================= GŁÓWNA LOGIKA =================

def main():
    print(f"🚀 BOT START: {datetime.now().strftime('%H:%M:%S')}")
    if not API_KEYS:
        print("❌ Brak kluczy API!"); return

    current_key_idx = get_current_key_idx()
    all_coupons = []
    if os.path.exists(COUPONS_FILE):
        try:
            with open(COUPONS_FILE, "r", encoding="utf-8") as f:
                all_coupons = json.load(f)
        except: pass
    
    already_sent_ids = [c['id'] for c in all_coupons]
    now_utc = datetime.now(timezone.utc)
    max_future = now_utc + timedelta(hours=48)

    for league, flag in SPORTS_CONFIG.items():
        stake, threshold = get_smart_stake(league)
        
        active_key = API_KEYS[current_key_idx]
        url = f"https://api.the-odds-api.com/v4/sports/{league}/odds/"
        params = {"apiKey": active_key, "regions": "eu", "markets": "h2h"}
        
        try:
            resp = requests.get(url, params=params, timeout=15)
            if resp.status_code == 429: # Limit klucza
                current_key_idx = (current_key_idx + 1) % len(API_KEYS)
                continue
            if resp.status_code != 200: continue
            data = resp.json()
        except: continue

        for event in data:
            if event['id'] in already_sent_ids: continue
            
            try:
                m_time = datetime.fromisoformat(event['commence_time'].replace("Z", "+00:00"))
                if m_time > max_future or m_time < now_utc: continue 
            except: continue

            # Zbieranie kursów
            prices = {} 
            for bookie in event['bookmakers']:
                for market in bookie['markets']:
                    if market['key'] == 'h2h':
                        for out in market['outcomes']:
                            prices.setdefault(out['name'], []).append(out['price'])

            # Szukanie Value
            best_choice, best_odds, max_val = None, 0, 0
            for name, p_list in prices.items():
                if name.lower() == "draw" or not p_list: continue
                
                max_p = max(p_list)
                avg_p = sum(p_list) / len(p_list)
                curr_val = max_p / avg_p
                
                # Progi bezpieczeństwa
                req_val = threshold
                if max_p >= 2.2: req_val += 0.03
                if max_p >= 3.2: req_val += 0.04
                
                if 1.85 <= max_p <= 5.0 and curr_val > req_val:
                    if curr_val > max_val:
                        max_val, best_odds, best_choice = curr_val, max_p, name

            if best_choice:
                # Formatowanie nazwy ligi
                l_name = league.replace("soccer_", "").replace("icehockey_", "").replace("_", " ").upper()
                s_icon = "🏒" if "icehockey" in league else "⚽"
                date_str = m_time.strftime('%d.%m | %H:%M')

                # TWÓJ NOWY WYGLĄD TYPU
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
                
                all_coupons.append({
                    "id": event['id'], "home": event['home_team'], "away": event['away_team'],
                    "outcome": best_choice, "odds": best_odds, "stake": stake,
                    "sport": league, "time": event['commence_time']
                })
                already_sent_ids.append(event['id'])

    save_current_key_idx(current_key_idx)
    with open(COUPONS_FILE, "w", encoding="utf-8") as f:
        json.dump(all_coupons, f, indent=4)
    
    print(f"✅ KONIEC. Aktywne kupony: {len(all_coupons)}")

if __name__ == "__main__":
    main()
