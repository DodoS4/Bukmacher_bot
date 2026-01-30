import os
import requests
import json
import time
from datetime import datetime, timedelta, timezone

# ================= KONFIGURACJA LIG =================
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
    "basketball_euroleague": "🏀",
    "tennis_atp_australian_open": "🎾",
    "tennis_wta_australian_open": "🎾"
}

# Pliki bazy danych
HISTORY_FILE = "history.json"
COUPONS_FILE = "coupons.json"
KEY_STATE_FILE = "key_index.txt"
BASE_STAKE = 350

# ================= PANCERNE POBIERANIE KLUCZY =================
def get_env_safe(name):
    """Pobiera zmienną środowiskową i czyści ją ze spacji."""
    val = os.environ.get(name) or os.getenv(name)
    return str(val).strip() if val and len(str(val).strip()) > 0 else None

def get_all_api_keys():
    keys = []
    main_key = get_env_safe("ODDS_KEY")
    if main_key: keys.append(main_key)
    for i in range(2, 11):
        k = get_env_safe(f"ODDS_KEY_{i}")
        if k: keys.append(k)
    return keys

# ================= OBSŁUGA TELEGRAMA =================
def send_telegram(message, mode="HTML"):
    token = get_env_safe("T_TOKEN")
    chat = get_env_safe("T_CHAT")

    if not token or not chat:
        print(f"⚠️ POMINIĘTO TELEGRAM: TOKEN={bool(token)}, CHAT={bool(chat)}")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat, 
        "text": message, 
        "parse_mode": mode,
        "disable_web_page_preview": True
    }
    
    try: 
        r = requests.post(url, json=payload, timeout=15)
        if r.status_code == 200:
            print("✅ Wiadomość wysłana na Telegram.")
        else:
            print(f"❌ Błąd Telegram API: {r.status_code} - {r.text}")
    except Exception as e:
        print(f"❌ Błąd połączenia z Telegram: {e}")

# ================= LOGIKA ZAKŁADÓW =================
def get_current_key_idx(num_keys):
    if num_keys == 0: return 0
    if os.path.exists(KEY_STATE_FILE):
        try:
            with open(KEY_STATE_FILE, "r") as f:
                return int(f.read().strip()) % num_keys
        except: return 0
    return 0

def save_current_key_idx(idx):
    with open(KEY_STATE_FILE, "w") as f:
        f.write(str(idx))

def get_smart_stake(league_key):
    """Dobieranie stawki na podstawie historycznych zysków ligi."""
    current_multiplier = 1.0
    threshold = 1.03
    history_profit = 0

    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
            league_profit = sum(m.get('profit', 0) for m in history if m.get('sport') == league_key)
            history_profit = league_profit
            
            if league_profit <= -700:
                current_multiplier, threshold = 0.5, 1.07
            elif league_profit <= -300:
                current_multiplier, threshold = 0.8, 1.05
            elif league_profit >= 1000:
                current_multiplier = 1.5
        except: pass
    
    final_stake = BASE_STAKE * current_multiplier
    # Twoja złota zasada dla NHL
    if "nhl" in league_key.lower():
        final_stake *= 1.2 if history_profit > 0 else 1.1

    return round(final_stake, 2), threshold

def main():
    print(f"🚀 START BOT PRO: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    api_keys = get_all_api_keys()
    token = get_env_safe("T_TOKEN")
    chat = get_env_safe("T_CHAT")
    
    print(f"🔑 STATUS: KEYS={len(api_keys)}, T_TOKEN={bool(token)}, T_CHAT={bool(chat)}")
    
    if not api_keys:
        print("❌ Błąd: Brak kluczy Odds API!")
        return

    current_key_idx = get_current_key_idx(len(api_keys))
    
    if os.path.exists(COUPONS_FILE):
        try:
            with open(COUPONS_FILE, "r", encoding="utf-8") as f:
                all_coupons = json.load(f)
        except: all_coupons = []
    else: all_coupons = []
    
    already_sent_ids = [c['id'] for c in all_coupons]
    now = datetime.now(timezone.utc)
    max_future = now + timedelta(hours=48)

    for league, flag_emoji in SPORTS_CONFIG.items():
        current_stake, base_threshold = get_smart_stake(league)
        print(f"📡 SKANOWANIE: {league.upper()}")
        
        data = None
        # Próba pobrania danych przy użyciu dostępnych kluczy
        for _ in range(len(api_keys)):
            active_key = api_keys[current_key_idx]
            url = f"https://api.the-odds-api.com/v4/sports/{league}/odds/"
            params = {"apiKey": active_key, "regions": "eu", "markets": "h2h"}
            try:
                resp = requests.get(url, params=params, timeout=15)
                if resp.status_code == 200:
                    data = resp.json()
                    break
                elif resp.status_code in [401, 429]:
                    current_key_idx = (current_key_idx + 1) % len(api_keys)
                else: break
            except:
                current_key_idx = (current_key_idx + 1) % len(api_keys)

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
                
                max_p, avg_p = max(prices), (sum(prices) / len(prices))
                curr_val = max_p / avg_p
                
                req_val = base_threshold
                if max_p >= 2.2: req_val += 0.03
                
                if 1.85 <= max_p <= 5.0 and curr_val > req_val:
                    if curr_val > max_val:
                        max_val, best_odds, best_choice = curr_val, max_p, name

            if best_choice:
                date_str = m_time.strftime('%d.%m | %H:%M')
                l_name = league.upper().replace("SOCCER_", "").replace("ICEHOCKEY_", "").replace("_", " ")
                s_icon = "🏒" if "icehockey" in league else "⚽"
                
                msg = (f"{s_icon} {flag_emoji} <b>{l_name}</b>\n"
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
