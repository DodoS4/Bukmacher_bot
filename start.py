import os
import requests
import json
import time
import random
from datetime import datetime, timedelta, timezone

# ================= PANEL STEROWANIA =================
BASE_STAKE = 250        # Twoja stawka bazowa
VYPLATA_PERCENT = 0.00  # <--- Zmień na np. 0.75 kiedy zrobisz wypłatę
# ====================================================

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
    payload = {
        "chat_id": chat, 
        "text": message, 
        "parse_mode": "HTML", 
        "disable_web_page_preview": True
    }
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
    print(f"✨ Betting Bot Professional Dawid")
    print(f"🚀 START: {datetime.now().strftime('%H:%M:%S')}")
    
    api_keys = []
    for i in range(1, 11):
        key_name = "ODDS_KEY" if i == 1 else f"ODDS_KEY_{i}"
        val = get_secret(key_name)
        if val: api_keys.append(val)
    
    if not api_keys:
        print("❌ Brak kluczy API!")
        return

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
    initial_count = len(already_sent)
    
    now = datetime.now(timezone.utc)
    max_future = now + timedelta(hours=72) # FILTR 3 DOBY

    for league, flag in SPORTS_CONFIG.items():
        stake, threshold = get_smart_stake(league)
        print(f"📡 Skan: {league.ljust(35)} | Stawka: {stake}")
        
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
            
            try:
                m_time_utc = datetime.fromisoformat(event['commence_time'].replace("Z", "+00:00"))
                if not (now < m_time_utc < max_future):
                    continue
                m_time = m_time_utc.astimezone(timezone(timedelta(hours=1)))
            except:
                continue

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
                league_display = league.upper().replace("SOCCER_", "").replace("ICEHOCKEY_", "").replace("_", " ")
                search_query = event['home_team'].split()[0]
                random_v = random.randint(1000, 9999)
                superbet_link = f"https://superbet.pl/wyszukiwanie?query={search_query}&v={random_v}"

                # IDENTYCZNY FORMAT WIADOMOŚCI TELEGRAM
                msg = (f"{flag} {flag} {league_display}\n"
                       f"━━━━━━━━━━━━━━━\n"
                       f"🏟 {event['home_team']} vs {event['away_team']}\n"
                       f"⏰ Start: {m_time.strftime('%d.%m | %H:%M')}\n\n"
                       f"✅ Typ: <b>{best_name}</b>\n"
                       f"📈 Kurs: <b>{best_odd}</b>\n"
                       f"💰 Stawka: <b>{stake} PLN</b>\n"
                       f"📊 Value: <b>+{round((max_val-1)*100, 1)}%</b>\n"
                       f"━━━━━━━━━━━━━━━\n\n"
                       f"🔗 <a href='{superbet_link}'>👉 OTWÓRZ W SUPERBET 👈</a>")
                
                send_telegram(msg)
                
                # ZAPIS KOMPLETNYCH DANYCH DLA SETTLE I STATS
                all_coupons.append({
                    "id": event['id'], 
                    "home": event['home_team'], 
                    "away": event['away_team'], 
                    "outcome": best_name,
                    "odds": best_odd,
                    "stake": stake,
                    "sport": league, 
                    "time": event['commence_time']
                })
                already_sent.append(event['id'])

    # SEKCJA DEBUG W LOGACH
    new_found = len(all_coupons) - initial_count
    print(f"\n{'='*40}")
    print(f"📊 PODSUMOWANIE SKANOWANIA")
    print(f"✅ Nowych okazji wysłanych: {new_found}")
    print(f"📂 Wszystkich aktywnych w coupons.json: {len(all_coupons)}")
    print(f"{'='*40}\n")

    with open(KEY_STATE_FILE, "w") as f: f.write(str(idx))
    with open(COUPONS_FILE, "w", encoding="utf-8") as f: json.dump(all_coupons, f, indent=4)

if __name__ == "__main__":
    main()
