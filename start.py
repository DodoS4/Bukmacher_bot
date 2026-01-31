import os
import requests
import json
import time
import urllib.parse
from datetime import datetime, timedelta, timezone

# ================= PANEL STEROWANIA =================
BASE_STAKE = 25         # Stawka bazowa pod bankroll 500 PLN
VYPLATA_PERCENT = 0.0   # Budujemy kulę śnieżną
# ====================================================

SPORTS_CONFIG = {
    "icehockey_nhl": "🏒", 
    "soccer_epl": "⚽",
    "soccer_germany_bundesliga": "🇩🇪",
    "soccer_italy_serie_a": "🇮🇹", 
    "soccer_spain_la_liga": "🇪🇸",
    "soccer_poland_ekstraklasa": "🇵🇱",
    "soccer_france_ligue_one": "🇫🇷",
    "basketball_euroleague": "🏀"
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
        "disable_web_page_preview": True  # Wyłączony podgląd, żeby link był czytelniejszy
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
            if raw_profit <= -700:
                current_multiplier, threshold = 0.5, 1.08
            elif raw_profit >= 1000:
                current_multiplier = 1.3
        except: pass
    
    final_stake = BASE_STAKE * current_multiplier
    if "icehockey" in league_key.lower():
        threshold -= 0.01 
        final_stake *= 1.25 
    return round(final_stake, 2), round(threshold, 3)

def main():
    print(f"🚀 START: {datetime.now().strftime('%H:%M:%S')}")
    
    api_keys = []
    for i in range(1, 11):
        key_name = "ODDS_KEY" if i == 1 else f"ODDS_KEY_{i}"
        val = get_secret(key_name)
        if val: api_keys.append(val)
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
    max_future = now + timedelta(hours=72)

    for league, flag in SPORTS_CONFIG.items():
        stake, threshold = get_smart_stake(league)
        print(f"📡 Skan: {league} | Stawka: {stake}")
        
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
            except: idx = (idx + 1) % len(api_keys)

        if not data: continue

        for event in data:
            if event['id'] in already_sent: continue
            try:
                m_time_utc = datetime.fromisoformat(event['commence_time'].replace("Z", "+00:00"))
                if not (now < m_time_utc < max_future): continue
                m_time = m_time_utc.astimezone(timezone(timedelta(hours=1)))
            except: continue

            prices = {out['name']: out['price'] for b in event.get('bookmakers', []) for m in b.get('markets', []) if m['key']=='h2h' for out in m['outcomes']}

            best_name, best_odd, max_val = None, 0, 0
            if len(prices) >= 2:
                avg_odd = sum(prices.values()) / len(prices)
                for name, price in prices.items():
                    if name.lower() == "draw": continue
                    val = price / avg_odd
                    if 1.80 <= price <= 4.50 and val > threshold:
                        if val > max_val: max_val, best_odd, best_name = val, price, name

            if best_name:
                # --- NAPRAWA LINKÓW ---
                # Czyścimy nazwę gospodarza, bierzemy tylko pierwszy człon (np. "Real" zamiast "Real Madrid")
                raw_home = event['home_team'].replace("FC", "").replace("United", "").replace("BC", "").strip()
                search_word = raw_home.split()[0]
                
                # Kodowanie URL
                encoded_search = urllib.parse.quote(search_word)
                superbet_link = f"https://superbet.pl/wyszukiwanie?query={encoded_search}"

                league_display = league.upper().replace("SOCCER_", "").replace("_", " ")
                msg = (f"{flag} <b>{league_display}</b>\n"
                       f"━━━━━━━━━━━━━━━\n"
                       f"🏟 {event['home_team']} - {event['away_team']}\n"
                       f"⏰ Start: {m_time.strftime('%d.%m | %H:%M')}\n\n"
                       f"🎯 Typ: <b>{best_name}</b>\n"
                       f"📈 Kurs: <b>{best_odd}</b>\n"
                       f"💰 Stawka: <b>{stake} PLN</b>\n"
                       f"📊 Value: <b>+{round((max_val-1)*100, 1)}%</b>\n"
                       f"━━━━━━━━━━━━━━━\n\n"
                       f"🔗 <a href='{superbet_link}'>👉 POSTAW W SUPERBET 👈</a>")
                
                send_telegram(msg)
                all_coupons.append({"id": event['id'], "home": event['home_team'], "away": event['away_team'], "outcome": best_name, "odds": best_odd, "stake": stake, "sport": league, "time": event['commence_time']})
                already_sent.append(event['id'])

    with open(KEY_STATE_FILE, "w") as f: f.write(str(idx))
    with open(COUPONS_FILE, "w", encoding="utf-8") as f: json.dump(all_coupons, f, indent=4)

if __name__ == "__main__": main()
