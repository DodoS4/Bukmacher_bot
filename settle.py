import os
import json
import requests
from datetime import datetime, timezone, timedelta

# --- KONFIGURACJA PLIKÓW ---
COUPONS_FILE = "coupons.json"
HISTORY_FILE = "history.json"
STATS_JSON_FILE = "stats.json"

# --- MAPOWANIE LIG (NAPRAWA BŁĘDÓW 404) ---
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
    """Wysyła wynik meczu na Telegram."""
    token = get_secret("T_TOKEN")
    # Używa dedykowanego kanału dla wyników lub głównego
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

def update_web_stats(history, bankroll, total_profit, active_count):
    now = datetime.now(timezone.utc)
    profit_24h = 0
    for m in history:
        t_str = m.get('time')
        if not t_str or t_str == "": continue 
        try:
            m_time = datetime.fromisoformat(t_str.replace("Z", "+00:00"))
            if now - m_time < timedelta(hours=24):
                profit_24h += float(m.get('profit', 0))
        except: continue
    stats_data = {
        "bankroll": round(bankroll, 2),
        "zysk_total": round(total_profit, 2),
        "zysk_24h": round(profit_24h, 2),
        "last_sync": now.strftime("%d.%m.%Y %H:%M"),
        "upcoming_val": active_count
    }
    with open(STATS_JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(stats_data, f, indent=4)

def settle_matches():
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f: history = json.load(f)
        with open(COUPONS_FILE, "r", encoding="utf-8") as f: active_coupons = json.load(f)
    except: return

    still_active, updated, settled_count = [], False, 0
    now = datetime.now(timezone.utc)
    print(f"\n--- RAPORT ROZLICZEŃ: {now.strftime('%H:%M:%S')} ---")

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
                    
                    stake = float(coupon.get('stake', 100))
                    profit = (stake * float(coupon['odds']) - stake) if is_win else -stake

                    # --- POWIADOMIENIE TELEGRAM ---
                    status_icon = "✅ <b>ZYSK</b>" if is_win else "❌ <b>STRATA</b>"
                    sport_emoji = "🏒" if "ice" in sport.lower() else "⚽"
                    msg = (f"{status_icon}\n"
                           f"━━━━━━━━━━━━━━━\n"
                           f"{sport_emoji} {coupon['home']} <b>{h_score}:{a_score}</b> {coupon['away']}\n"
                           f"🎯 Typ: <b>{coupon['outcome']}</b> (@{coupon['odds']})\n"
                           f"💰 Profit: <b>{profit:+.2f} PLN</b>\n"
                           f"━━━━━━━━━━━━━━━")
                    send_telegram_result(msg)

                    print(f"{'✅ ZYSK' if is_win else '❌ STRATA'}: {coupon['home']} {h_score}:{a_score} | {profit:+.2f} PLN")
                    history.append({**coupon, "status": "WIN" if is_win else "LOSS", "score": f"{h_score}:{a_score}", "profit": round(profit, 2), "time": now.isoformat()})
                    updated = True; settled_count += 1
                except: still_active.append(coupon)
            else:
                st_str = coupon.get('commence_time') or coupon.get('date')
                if st_str:
                    try:
                        st = datetime.fromisoformat(st_str.replace("Z", "+00:00"))
                        if (now - st) > timedelta(hours=48):
                            print(f"🔄 ZWROT: {coupon['home']} - {coupon['away']}")
                            history.append({**coupon, "status": "VOID", "score": "CANCEL", "profit": 0.00, "time": now.isoformat()})
                            updated = True; settled_count += 1; continue
                    except: pass
                still_active.append(coupon)

    if updated:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f: json.dump(history, f, indent=4)
        with open(COUPONS_FILE, "w", encoding="utf-8") as f: json.dump(still_active, f, indent=4)

    total_profit = sum(float(m.get('profit', 0)) for m in history)
    update_web_stats(history, 5000 + total_profit, total_profit, len(still_active))
    print(f"--- ZAKOŃCZONO: Rozliczono {settled_count} ---\n")

if __name__ == "__main__":
    settle_matches()
