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

HISTORY_FILE = "history.json"
COUPONS_FILE = "coupons.json"
KEY_STATE_FILE = "key_index.txt"
BASE_STAKE = 350

# ================= FUNKCJA POBIERANIA SEKRETÓW =================
def get_secret(name):
    """Pobiera sekret i upewnia się, że nie jest pusty."""
    val = os.environ.get(name) or os.getenv(name)
    if val:
        return str(val).strip()
    return None

# ================= OBSŁUGA TELEGRAMA =================
def send_telegram(message, mode="HTML"):
    """Wysyła wiadomość, pobierając klucze w locie."""
    token = get_secret("T_TOKEN")
    chat = get_secret("T_CHAT")

    if not token or not chat:
        # Ten print pokaże nam w logach GitHub Actions co jest nie tak
        print(f"DEBUG_FAIL: T_TOKEN={bool(token)}, T_CHAT={bool(chat)}")
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
            print("✅ Powiadomienie wysłane.")
        else:
            print(f"❌ Telegram API Error: {r.status_code} - {r.text}")
    except Exception as e:
        print(f"❌ Błąd połączenia z Telegramem: {e}")

# ================= LOGIKA ZASOBÓW =================
def get_all_keys():
    keys = []
    k1 = get_secret("ODDS_KEY")
    if k1: keys.append(k1)
    for i in range(2, 11):
        ki = get_secret(f"ODDS_KEY_{i}")
        if ki: keys.append(ki)
    return keys

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
    """Oblicza stawkę na podstawie Twoich zysków."""
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
    if "nhl" in league_key.lower():
        final_stake *= 1.2 if history_profit > 0 else 1.1

    return round(final_stake, 2), threshold

# ================= GŁÓWNA PĘTLA =================
def main():
    print(f"🚀 BOT START: {datetime.now().strftime('%H:%M:%S')}")
    
    api_keys = get_all_keys()
    if not api_keys:
        print("❌ Błąd: Brak kluczy API (ODDS_KEY)!")
        return

    # Sprawdzenie obecności kluczy Telegrama na starcie
    token_check = get_secret("T_TOKEN")
    chat_check = get_secret("T_CHAT")
    print(f"🔍 Status kluczy: API={len(api_keys)}, Telegram={bool(token_check and chat_check)}")

    idx = get_current_key_idx(len(api_keys))
    
    # Ładowanie kuponów
    all_coupons = []
    if os.path.exists(COUPONS_FILE):
        try:
            with open(COUPONS_FILE, "r", encoding="utf-8") as f:
                all_coupons = json.load(f)
        except: pass
    
    already_sent = [c['id'] for c in all_coupons]
    now = datetime.now(timezone.utc)
    max_future = now + timedelta(hours=48)

    for league, flag in SPORTS_CONFIG.items():
        stake, threshold = get_smart_stake(league)
        print(f"📡 Skan: {league}")
        
        data = None
        for _ in range(len(api_keys)):
            current_key = api_keys[idx]
            url = f"https://api.the-odds-api.com/v4/sports/{league}/odds/"
            params = {"apiKey": current_key, "regions": "eu", "markets": "h2h"}
            try:
                r = requests.get(url, params=params, timeout=15)
                if r.status_code == 200:
                    data = r.json()
                    break
                elif r.status_code in [401, 429]:
                    idx = (idx + 1) % len(api_keys)
                else: break
            except:
                idx = (idx + 1) % len(api_keys)

        if not data: continue

        for event in data:
            if event['id'] in already_sent: continue
            
            try:
                m_time = datetime.fromisoformat(event['commence_time'].replace("Z", "+00:00"))
                if not (now < m_time < max_future): continue 
            except: continue

            # Analiza kursów
            prices = {}
            for bookie in event.get('bookmakers', []):
                for market in bookie.get('markets', []):
                    if market['key'] == 'h2h':
                        for out in market['outcomes']:
                            if out['name'] not in prices: prices[out['name']] = []
                            prices[out['name']].append(out['price'])

            best_name, best_odd, max_val = None, 0, 0
            for name, p_list in prices.items():
                if name.lower() == "draw": continue
                
                m_p, a_p = max(p_list), sum(p_list)/len(p_list)
                val = m_p / a_p
                
                req = threshold + (0.03 if m_p >= 2.2 else 0)
                
                if 1.85 <= m_p <= 5.0 and val > req:
                    if val > max_val:
                        max_val, best_odd, best_name = val, m_p, name

            if best_name:
                l_header = league.upper().replace("SOCCER_", "").replace("ICEHOCKEY_", "").replace("_", " ")
                icon = "🏒" if "icehockey" in league else "⚽"
                
                msg = (f"{icon} {flag} <b>{l_header}</b>\n"
                       f"━━━━━━━━━━━━━━━\n"
                       f"🏟 <b>{event['home_team']}</b> vs <b>{event['away_team']}</b>\n"
                       f"⏰ Start: {m_time.strftime('%d.%m | %H:%M')}\n\n"
                       f"✅ Typ: <b>{best_name}</b>\n"
                       f"📈 Kurs: <b>{best_odd}</b>\n"
                       f"💰 Stawka: <b>{stake} PLN</b>\n"
                       f"📊 Value: <b>+{round((max_val-1)*100, 1)}%</b>\n"
                       f"━━━━━━━━━━━━━━━")
                
                send_telegram(msg)
                
                all_coupons.append({
                    "id": event['id'], "home": event['home_team'], "away": event['away_team'],
                    "outcome": best_name, "odds": best_odd, "stake": stake,
                    "sport": league, "time": event['commence_time']
                })
                already_sent.append(event['id'])

    save_current_key_idx(idx)
    with open(COUPONS_FILE, "w", encoding="utf-8") as f:
        json.dump(all_coupons, f, indent=4)
    print(f"✅ Koniec. Aktywne: {len(all_coupons)}")

if __name__ == "__main__":
    main()
