import os
import requests
import json
import time
import random
from datetime import datetime, timedelta, timezone

# ================= KONFIGURACJA =================
BASE_STAKE = 250        # Twoja stawka bazowa
VYPLATA_PERCENT = 0.00  # <--- Zmień na np. 0.75 kiedy zrobisz wypłatę
# ===============================================

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

def get_secret(name):
    val = os.environ.get(name) or os.getenv(name)
    return str(val).strip() if val else None

def send_telegram(message):
    token = get_secret("T_TOKEN")
    chat = get_secret("T_CHAT")
    if not token or not chat: return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat, "text": message, "parse_mode": "HTML", "disable_web_page_preview": True}
    try: requests.post(url, json=payload, timeout=15)
    except: pass

def get_smart_stake(league_key):
    current_multiplier = 1.0
    threshold = 1.035 
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
            raw_profit = sum(m.get('profit', 0) for m in history if m.get('sport') == league_key)
            # Uwzględnienie wypłaty w stawkowaniu
            effective_profit = raw_profit * (1 - VYPLATA_PERCENT)
            
            if effective_profit <= -700:
                current_multiplier, threshold = 0.5, 1.08
            elif effective_profit >= 3000:
                current_multiplier = 1.6
            elif effective_profit >= 1000:
                current_multiplier = 1.3
        except: pass
    final_stake = BASE_STAKE * current_multiplier
    if "icehockey" in league_key.lower():
        threshold -= 0.01 
        final_stake *= 1.25 
    return round(final_stake, 2), round(threshold, 3)

def main():
    print(f"✨ Betting Bot Professional Dawid / run-bot")
    print(f"🚀 START BOT PRO: {datetime.now().strftime('%H:%M:%S')}")
    
    api_keys = []
    k1 = get_secret("ODDS_KEY")
    if k1: api_keys.append(k1)
    for i in range(2, 11):
        ki = get_secret(f"ODDS_KEY_{i}")
        if ki: api_keys.append(ki)
    
    if not api_keys: return

    if os.path.exists(KEY_STATE_FILE):
        try:
            with open(KEY_STATE_FILE, "r") as f:
                idx = int(f.read().strip()) % len(api_keys)
        except: idx = 0
    else: idx = 0

    all_coupons = []
    if os.path.exists(COUPONS_FILE):
        try:
            with open(COUPONS_FILE, "r", encoding="utf-8") as f:
                all_coupons = json.load(f)
        except: pass
    
    already_sent = [c['id'] for c in all_coupons]
    now = datetime.now(timezone.utc)

    for league, flag in SPORTS_CONFIG.items():
        stake, threshold = get_smart_stake(league)
        # Przywrócenie Twojego stylu logowania
        print(f"📡 Skan: {league} (Stawka: {stake}, Próg: {threshold})")
        
        data = None
        for _ in range(len(api_keys)):
            url = f"https://api.the-odds-api.com/v4/sports/{league}/odds/"
            params = {"apiKey": api_keys[idx], "regions": "eu", "markets": "h2h"}
            try:
                resp = requests.get(url, params=params, timeout=15)
                if resp.status_code == 200:
                    data = resp.json()
                    break
                idx = (idx + 1) % len(api_keys)
            except:
                idx = (idx + 1) % len(api_keys)

        if not data: continue

        for event in data:
            if event['id'] in already_sent: continue
            
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
                if 1.80 <= m_p <= 4.50 and val > threshold:
                    if val > max_val:
                        max_val, best_odd, best_name = val, m_p, name

            if best_name:
                search_query = event['home_team'].split()[0]
                random_v = random.randint(1000, 9999)
                superbet_link = f"https://superbet.pl/wyszukiwanie?query={search_query}&v={random_v}"

                msg = (f"{'🏒' if 'ice' in league else '⚽'} {flag} <b>{league.upper()}</b>\n"
                       f"━━━━━━━━━━━━━━━\n"
                       f"🏟 <b>{event['home_team']}</b> vs <b>{event['away_team']}</b>\n\n"
                       f"✅ Typ: <b>{best_name}</b>\n"
                       f"📈 Kurs: <b>{best_odd}</b>\n"
                       f"💰 Stawka: <b>{stake} PLN</b>\n"
                       f"📊 Value: <b>+{round((max_val-1)*100, 1)}%</b>\n\n"
                       f"🔗 <a href='{superbet_link}'>👉 OTWÓRZ W SUPERBET 👈</a>\n"
                       f"━━━━━━━━━━━━━━━")
                
                send_telegram(msg)
                all_coupons.append({"id": event['id'], "sport": league, "profit": 0}) # uproszczone dla przykładu
                already_sent.append(event['id'])

    print(f"✅ Koniec. Aktywne: {len(all_coupons)}")
    with open(KEY_STATE_FILE, "w") as f: f.write(str(idx))

if __name__ == "__main__":
    main()
