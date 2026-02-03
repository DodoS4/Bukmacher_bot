import os
import requests
import json
import time
from datetime import datetime, timedelta, timezone

# ================= KONFIGURACJA LIG (ZAKTUALIZOWANA) =================
SPORTS_CONFIG = {
    "icehockey_nhl": "🏒", 
    "icehockey_sweden_allsvenskan": "🇸🇪",
    "icehockey_sweden_shl": "🇸🇪",
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
    "soccer_scotland_premiership": "🏴",
    "soccer_efl_championship": "🏴",
    "basketball_euroleague": "🏀",
    "tennis_atp_australian_open": "🎾",
    "tennis_wta_australian_open": "🎾"
}

HISTORY_FILE = "history.json"
COUPONS_FILE = "coupons.json"
KEY_STATE_FILE = "key_index.txt"
BASE_STAKE = 250

# ================= POMOCNICZE =================
def get_secret(name):
    val = os.environ.get(name) or os.getenv(name)
    return str(val).strip() if val else None

def send_telegram(message, mode="HTML"):
    token = get_secret("T_TOKEN")
    chat = get_secret("T_CHAT")
    if not token or not chat: return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat, "text": message, "parse_mode": mode}
    try: requests.post(url, json=payload, timeout=15)
    except: pass

def get_smart_stake(league_key):
    current_multiplier, threshold, history_profit = 1.0, 1.035, 0
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
            league_profit = sum(m.get('profit', 0) for m in history if m.get('sport') == league_key)
            history_profit = league_profit
            if league_profit <= -700: current_multiplier, threshold = 0.5, 1.08
            elif league_profit >= 3000: current_multiplier = 1.6
            elif league_profit >= 1000: current_multiplier = 1.3
        except: pass
    final_stake = BASE_STAKE * current_multiplier
    if "icehockey" in league_key.lower():
        threshold -= 0.01 
        if history_profit > 0: final_stake *= 1.25 
    return round(final_stake, 2), round(threshold, 3)

def get_all_keys():
    keys = []
    for i in range(1, 11):
        name = "ODDS_KEY" if i == 1 else f"ODDS_KEY_{i}"
        val = get_secret(name)
        if val: keys.append(val)
    return keys

# ================= MAIN =================
def main():
    print(f"🚀 --- START BOT PRO: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")
    api_keys = get_all_keys()
    if not api_keys: 
        print("❌ BŁĄD: Brak kluczy API!")
        return

    try:
        with open(KEY_STATE_FILE, "r") as f: idx = int(f.read().strip()) % len(api_keys)
    except: idx = 0

    all_coupons = []
    if os.path.exists(COUPONS_FILE):
        try:
            with open(COUPONS_FILE, "r", encoding="utf-8") as f: all_coupons = json.load(f)
        except: pass
    
    already_sent = [c['id'] for c in all_coupons]
    now = datetime.now(timezone.utc)
    max_future = now + timedelta(hours=48)
    new_bets_count = 0

    for league, flag in SPORTS_CONFIG.items():
        print(f"\n🔍 Skanowanie: {flag} {league.upper()}...")
        stake, threshold = get_smart_stake(league)
        data = None
        
        # Próba pobrania danych (NAPRAWIONY URL I LOGIKA BŁĘDÓW)
        for _ in range(len(api_keys)):
            # USUNIĘTO końcowy slash, który powodował 404
            url = f"https://api.the-odds-api.com/v4/sports/{league}/odds"
            params = {"apiKey": api_keys[idx], "regions": "eu", "markets": "h2h", "oddsFormat": "decimal"}
            
            try:
                print(f"  📡 Klucz API #{idx+1}...", end=" ")
                resp = requests.get(url, params=params, timeout=15)
                
                if resp.status_code == 200:
                    data = resp.json()
                    print("OK!")
                    break
                elif resp.status_code == 404:
                    # 404 często oznacza brak aktywnej oferty na tę ligę
                    print("Brak meczów (404)")
                    break 
                elif resp.status_code == 429:
                    print("Limit klucza przekroczony (429)")
                    idx = (idx + 1) % len(api_keys)
                else:
                    print(f"Błąd {resp.status_code}")
                    idx = (idx + 1) % len(api_keys)
            except Exception as e:
                print(f"Błąd połączenia: {e}")
                idx = (idx + 1) % len(api_keys)

        if not data:
            continue

        print(f"  📈 Znaleziono {len(data)} meczów.")
        
        for event in data:
            if event['id'] in already_sent: continue
            
            try:
                # Stabilniejszy parsing daty
                m_time = datetime.fromisoformat(event['commence_time'].replace("Z", "+00:00"))
                if not (now < m_time < max_future):
                    continue 
                m_display = m_time.astimezone(timezone(timedelta(hours=1)))
            except: continue

            prices = {}
            for bookie in event.get('bookmakers', []):
                for market in bookie.get('markets', []):
                    if market['key'] == 'h2h':
                        for out in market['outcomes']:
                            if out['name'] not in prices: prices[out['name']] = []
                            prices[out['name']].append(out['price'])

            best_name, best_odd, max_val = None, 0, 0
            for name, p_list in prices.items():
                if name.lower() == "draw" or len(p_list) < 3: continue
                m_p, a_p = max(p_list), sum(p_list)/len(p_list)
                val = m_p / a_p
                
                req = threshold
                if m_p >= 2.5: req += 0.02 
                
                if 1.80 <= m_p <= 4.50:
                    if val > req:
                        if val > max_val:
                            max_val, best_odd, best_name = val, m_p, name

            if best_name:
                l_name = league.upper().replace("SOCCER_", "").replace("ICEHOCKEY_", "").replace("_", " ")
                print(f"  🎯 TYP! {event['home_team']} - {best_name} @{best_odd}")
                
                msg = (f"{'🏒' if 'ice' in league else '⚽'} {flag} <b>{l_name}</b>\n"
                       f"━━━━━━━━━━━━━━━\n"
                       f"🏟 <b>{event['home_team']}</b> vs <b>{event['away_team']}</b>\n"
                       f"⏰ Start: {m_display.strftime('%d.%m | %H:%M')}\n\n"
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
                new_bets_count += 1

    with open(KEY_STATE_FILE, "w") as f: f.write(str(idx))
    with open(COUPONS_FILE, "w", encoding="utf-8") as f:
        json.dump(all_coupons, f, indent=4)
    
    print(f"\n✅ KONIEC. Nowych typów: {new_bets_count}")

if __name__ == "__main__":
    main()
