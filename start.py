import os
import requests
import json
from datetime import datetime, timedelta, timezone
from stats import generate_stats

# ================= KONFIGURACJA LIG (USUNIĘTO KOSZYKÓWKĘ) =================
SPORTS_CONFIG = {
    "icehockey_nhl": "🏒", "icehockey_sweden_hockeyallsvenskan": "🇸🇪",
    "icehockey_finland_liiga": "🇫🇮", "icehockey_germany_del": "🇩🇪",
    "icehockey_czech_extraliga": "🇨🇿", "icehockey_switzerland_nla": "🇨🇭",
    "soccer_epl": "⚽", "soccer_germany_bundesliga": "🇩🇪",
    "soccer_italy_serie_a": "🇮🇹", "soccer_spain_la_liga": "🇪🇸",
    "soccer_poland_ekstraklasa": "🇵🇱", "soccer_france_ligue_one": "🇫🇷",
    "soccer_portugal_primeira_liga": "🇵🇹"
}

# ================= KONFIGURACJA API I PLIKÓW =================
API_KEYS = [os.getenv(f"ODDS_KEY_{i}" if i > 1 else "ODDS_KEY") for i in range(1, 11)]
API_KEYS = [k for k in API_KEYS if k and len(k) > 10]

TELEGRAM_TOKEN = os.getenv("T_TOKEN")
TELEGRAM_CHAT = os.getenv("T_CHAT")           
TELEGRAM_RESULTS = os.getenv("T_CHAT_RESULTS") 

HISTORY_FILE = "history.json"
COUPONS_FILE = "coupons.json"
KEY_STATE_FILE = "key_index.txt"
BANKROLL_FILE = "bankroll.json"  # PLIK Z TWOIM SALDEM

# --- PARAMETRY CHALLENGE ---
START_BANKROLL = 100.0
STAKE_PERCENT = 0.05  # 5% KULA ŚNIEŻNA
MIN_STAKE = 2.0      # Minimalna stawka u buka

# ================= FUNKCJE POMOCNICZE =================

def get_current_bankroll():
    """Pobiera aktualny stan kasy z pliku."""
    if os.path.exists(BANKROLL_FILE):
        try:
            with open(BANKROLL_FILE, "r") as f:
                data = json.load(f)
                return float(data.get("balance", START_BANKROLL))
        except: return START_BANKROLL
    return START_BANKROLL

def send_telegram(message, mode="HTML", is_stats=False):
    if not TELEGRAM_TOKEN: return
    target_chat = TELEGRAM_RESULTS if (is_stats and TELEGRAM_RESULTS) else TELEGRAM_CHAT
    if not target_chat: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": target_chat, "text": message, "parse_mode": mode}, timeout=10)
    except: pass

def get_smart_stake(league_key):
    """Oblicza stawkę 5% z aktualnego bankrolla (EFEKT KULI ŚNIEŻNEJ)"""
    current_balance = get_current_bankroll()
    
    # Podstawowe 5%
    stake = current_balance * STAKE_PERCENT
    
    # Threshold (próg wejścia) - zachowujemy Twoją logikę zyskowności ligi
    threshold = 1.03
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                hist = json.load(f)
                prof = sum(m['profit'] for m in hist if m.get('sport') == league_key)
                if prof <= -700: threshold = 1.07
                elif prof <= -300: threshold = 1.05
        except: pass
    
    # Bonus dla NHL (z Twojego starego kodu)
    if "nhl" in league_key.lower(): 
        stake *= 1.2
        
    return round(max(stake, MIN_STAKE), 2), threshold

def clean_old_coupons(coupons):
    now = datetime.now(timezone.utc)
    original_count = len(coupons)
    cleaned = [c for c in coupons if datetime.fromisoformat(c['time'].replace("Z", "+00:00")) > now - timedelta(hours=48)]
    return cleaned

# ================= GŁÓWNA LOGIKA =================

def main():
    print(f"🚀 START CHALLENGE 100 PLN (5% STAKE)")
    if not API_KEYS:
        print("❌ Błąd: Brak kluczy API!")
        return

    try:
        with open(KEY_STATE_FILE, "r") as f: curr_idx = int(f.read().strip()) % len(API_KEYS)
    except: curr_idx = 0
    
    if os.path.exists(COUPONS_FILE):
        try:
            with open(COUPONS_FILE, "r", encoding="utf-8") as f: all_coupons = json.load(f)
        except: all_coupons = []
    else: all_coupons = []
    
    initial_ids = {c['id'] for c in all_coupons}
    now = datetime.now(timezone.utc)
    max_future = now + timedelta(hours=48)

    for league, flag in SPORTS_CONFIG.items():
        stake, threshold = get_smart_stake(league)
        print(f"📡 Skanuję: {league.upper()} | Bieżąca stawka: {stake} PLN")
        
        data = None
        for _ in range(len(API_KEYS)):
            url = f"https://api.the-odds-api.com/v4/sports/{league}/odds/"
            try:
                resp = requests.get(url, params={"apiKey": API_KEYS[curr_idx], "regions": "eu", "markets": "h2h"}, timeout=15)
                if resp.status_code == 200:
                    data = resp.json()
                    break
                curr_idx = (curr_idx + 1) % len(API_KEYS)
            except:
                curr_idx = (curr_idx + 1) % len(API_KEYS)

        if not data: continue

        for event in data:
            if event['id'] in initial_ids: continue
            
            try:
                m_time = datetime.fromisoformat(event['commence_time'].replace("Z", "+00:00"))
                if m_time < now or m_time > max_future: continue
            except: continue

            prices = {}
            for b in event['bookmakers']:
                for m in b['markets']:
                    if m['key'] == 'h2h':
                        for o in m['outcomes']:
                            prices.setdefault(o['name'], []).append(o['price'])

            best_o, best_p, max_v = None, 0, 0
            for name, p_list in prices.items():
                if name.lower() == "draw" or not p_list: continue
                mx, av = max(p_list), sum(p_list)/len(p_list)
                val = mx / av
                req = threshold + (0.03 if mx >= 2.2 else 0) + (0.04 if mx >= 3.2 else 0)
                
                if 1.85 <= mx <= 5.0 and val > req:
                    if val > max_v: max_v, best_p, best_o = val, mx, name

            if best_o:
                # Nagłówek dynamiczny (⚽ lub 🏒)
                sport_icon = "🏒" if "icehockey" in league else "⚽"
                msg = (f"{sport_icon} {flag} <b>{league.upper()}</b>\n"
                       f"━━━━━━━━━━━━━━━\n"
                       f"🏟 <b>{event['home_team']} - {event['away_team']}</b>\n"
                       f"⏰ Start: {m_time.strftime('%d.%m | %H:%M')}\n\n"
                       f"✅ Typ: <b>{best_o}</b>\n"
                       f"📈 Kurs: <b>{best_p}</b>\n"
                       f"💰 Stawka: <b>{stake} PLN</b> (5%)\n"
                       f"📊 Value: <b>+{round((max_v-1)*100, 1)}%</b>\n"
                       f"━━━━━━━━━━━━━━━")
                
                send_telegram(msg, is_stats=False)
                
                all_coupons.append({
                    "id": event['id'], "sport": league, "home": event['home_team'], 
                    "away": event['away_team'], "outcome": best_o, "odds": best_p, 
                    "stake": stake, "time": event['commence_time']
                })
                initial_ids.add(event['id'])
                
                with open(COUPONS_FILE, "w", encoding="utf-8") as f:
                    json.dump(all_coupons, f, indent=4)

    all_coupons = clean_old_coupons(all_coupons)
    with open(COUPONS_FILE, "w", encoding="utf-8") as f:
        json.dump(all_coupons, f, indent=4)

    with open(KEY_STATE_FILE, "w") as f: f.write(str(curr_idx))
    
    # Raport wysyłany po sesji
    print(f"📊 Generuję raport...")
    report = generate_stats()
    if report and "Błąd" not in report:
        send_telegram(report, mode="Markdown", is_stats=True)

    print(f"✅ KONIEC. Aktywne typy: {len(all_coupons)}")

if __name__ == "__main__":
    main()
