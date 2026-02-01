import os
import json
import requests
from datetime import datetime, timezone, timedelta

# --- KONFIGURACJA PLIKÓW ---
COUPONS_FILE = "coupons.json"
HISTORY_FILE = "history.json"
STATS_JSON_FILE = "stats.json"

LEAGUE_MAP = {
    "icehockey_sweden_hockeyallsvenskan": "icehockey_sweden_allsvenskan",
    "icehockey_finland_liiga": "icehockey_finland_liiga",
    "icehockey_germany_del": "icehockey_germany_del",
    "soccer_turkey_super_lig": "soccer_turkey_super_league"
}

def get_secret(name):
    val = os.environ.get(name) or os.getenv(name)
    return str(val).strip() if val else None

def send_telegram_result(message):
    token = get_secret("T_TOKEN")
    chat = get_secret("T_CHAT_RESULTS") or get_secret("T_CHAT")
    if not token or not chat: return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat, "text": message, "parse_mode": "HTML"}
    try: requests.post(url, json=payload, timeout=15)
    except: pass

def get_api_keys():
    keys = []
    first = os.getenv('ODDS_KEY')
    if first: keys.append(first.strip())
    for i in range(2, 11):
        k = os.getenv(f'ODDS_KEY_{i}') or os.getenv(f'ODDS_KEY{i}')
        if k: keys.append(k.strip())
    return keys

API_KEYS = get_api_keys()
current_key_index = 0

def get_api_scores(sport):
    global current_key_index
    if not API_KEYS: return []
    sport_api = LEAGUE_MAP.get(sport.lower(), sport.lower())
    for _ in range(len(API_KEYS)):
        api_key = API_KEYS[current_key_index]
        url = f"https://api.the-odds-api.com/v4/sports/{sport_api}/scores/?apiKey={api_key}&daysFrom=3"
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200: return response.json()
            elif response.status_code in [401, 429]:
                current_key_index = (current_key_index + 1) % len(API_KEYS)
                continue
            else: return []
        except:
            current_key_index = (current_key_index + 1) % len(API_KEYS)
    return []

def update_web_stats(bankroll_from_main, total_profit_from_main, active_count):
    """Główna funkcja naprawcza dla statystyk i wykresu."""
    now = datetime.now(timezone.utc)
    history = []
    
    # KROK 1: Wymuś odczyt historii, aby obrót nie był zerem
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)

    profit_24h = 0
    total_turnover = 0
    temp_bankroll = 5000.0
    graph_data = [5000.0] 

    # KROK 2: Przelicz wszystko chronologicznie
    history_sorted = sorted(history, key=lambda x: x.get('time', ''))

    for m in history_sorted:
        profit = float(m.get('profit', 0))
        # Szukamy stawki w kuponie, jeśli brak - standard 250 PLN
        stake = float(m.get('stake') or m.get('stawka') or 250)
        
        total_turnover += stake
        temp_bankroll += profit
        graph_data.append(round(temp_bankroll, 2))
        
        t_str = m.get('time')
        if t_str:
            try:
                m_time = datetime.fromisoformat(t_str.replace("Z", "+00:00"))
                if now - m_time < timedelta(hours=24):
                    profit_24h += profit
            except: continue

    # KROK 3: Przygotuj dane dla Dashboardu
    stats_data = {
        "bankroll": round(temp_bankroll, 2),
        "zysk_total": round(temp_bankroll - 5000.0, 2),
        "zysk_24h": round(profit_24h, 2),
        "obrot": round(total_turnover, 2),
        "yield": round(((temp_bankroll - 5000.0) / total_turnover * 100), 2) if total_turnover > 0 else 0,
        "last_sync": now.strftime("%d.%m.%Y %H:%M"),
        "upcoming_val": active_count,
        "history_graph": graph_data[-100:] 
    }
    
    with open(STATS_JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(stats_data, f, indent=4)
    print(f"--- STATS UPDATED: Obrót: {total_turnover} PLN, Punkty: {len(graph_data)} ---")

def settle_matches():
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r", encoding="utf-8") as f: history = json.load(f)
        else: history = []
        
        if not os.path.exists(COUPONS_FILE): return
        with open(COUPONS_FILE, "r", encoding="utf-8") as f: active_coupons = json.load(f)
    except: return

    still_active, updated = [], False
    now = datetime.now(timezone.utc)
    
    sports_to_check = list(set(c['sport'] for c in active_coupons))
    for sport in sports_to_check:
        scores_data = get_api_scores(sport)
        for coupon in [c for c in active_coupons if c['sport'] == sport]:
            match = next((s for s in scores_data if 
                          (coupon['home'].lower() in s['home_team'].lower()) and 
                          (s.get('completed') or s.get('scores'))), None)
            
            if match and match.get('scores'):
                try:
                    scores = match['scores']
                    h_score = int(next(s['score'] for s in scores if s['name'] == match['home_team']))
                    a_score = int(next(s['score'] for s in scores if s['name'] == match['away_team']))
                    
                    winner = match['home_team'] if h_score > a_score else (match['away_team'] if a_score > h_score else "DRAW")
                    is_win = (coupon['outcome'].lower() in winner.lower()) if coupon['outcome'] != "DRAW" else (winner == "DRAW")
                    
                    stake = float(coupon.get('stake', 250))
                    odds = float(coupon['odds'])
                    profit = (stake * odds - stake) if is_win else -stake

                    status_icon = "✅ <b>ZYSK</b>" if is_win else "❌ <b>STRATA</b>"
                    msg = (f"{status_icon}\n{coupon['home']} {h_score}:{a_score} {coupon['away']}\n"
                           f"Typ: {coupon['outcome']} (@{odds})\nProfit: {profit:+.2f} PLN")
                    send_telegram_result(msg)

                    history.append({**coupon, "status": "WIN" if is_win else "LOSS", "score": f"{h_score}:{a_score}", "profit": round(profit, 2), "time": now.isoformat()})
                    updated = True
                except: still_active.append(coupon)
            else:
                still_active.append(coupon)

    if updated:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f: json.dump(history, f, indent=4)
        with open(COUPONS_FILE, "w", encoding="utf-8") as f: json.dump(still_active, f, indent=4)

    total_profit = sum(float(m.get('profit', 0)) for m in history)
    update_web_stats(5000 + total_profit, total_profit, len(still_active))

if __name__ == "__main__":
    settle_matches()
