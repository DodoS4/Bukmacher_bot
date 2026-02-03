import os
import json
import requests
from datetime import datetime, timezone, timedelta

# --- KONFIGURACJA PLIKÓW ---
COUPONS_FILE = "coupons.json"
HISTORY_FILE = "history.json"
STATS_JSON_FILE = "stats.json"

def get_secret(name):
    val = os.environ.get(name) or os.getenv(name)
    return str(val).strip() if val else None

def send_telegram_results(message):
    token = get_secret("T_TOKEN")
    chat = get_secret("T_CHAT_RESULTS") or get_secret("T_CHAT")
    if not token or not chat: return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat, "text": message, "parse_mode": "HTML"}
    try: requests.post(url, json=payload, timeout=15)
    except: pass

def get_all_api_keys():
    keys = []
    for i in range(1, 11):
        key_name = "ODDS_KEY" if i == 1 else f"ODDS_KEY_{i}"
        val = os.getenv(key_name)
        if val: keys.append(val)
    return keys

def get_match_results(sport, keys):
    for key in keys:
        # POPRAWKA: Usunięto końcowy slash, aby uniknąć błędu 404
        url = f"https://api.the-odds-api.com/v4/sports/{sport}/scores"
        params = {"apiKey": key, "daysFrom": 3}
        try:
            resp = requests.get(url, params=params, timeout=15)
            if resp.status_code == 200: return resp.json()
        except: continue
    return None

def generate_report(history, remaining_count):
    now = datetime.now(timezone.utc)
    base_capital = 5000.0
    
    total_profit = 0.0
    total_staked = 0.0
    profit_24h = 0.0
    graph_data = [base_capital]
    
    history_sorted = sorted(history, key=lambda x: x.get('time', ''))

    for m in history_sorted:
        p = float(m.get('profit', 0))
        s = float(m.get('stake') or m.get('stawka') or 250)
        
        total_profit += p
        total_staked += s
        graph_data.append(round(base_capital + total_profit, 2))
        
        t_str = m.get('time')
        if t_str:
            try:
                m_time = datetime.fromisoformat(t_str.replace("Z", "+00:00"))
                if (now - m_time) < timedelta(hours=24):
                    profit_24h += p
            except: continue

    bankroll = base_capital + total_profit
    yield_val = (total_profit / total_staked * 100) if total_staked > 0 else 0
    
    stats_data = {
        "bankroll": round(bankroll, 2),
        "zysk_total": round(total_profit, 2),
        "zysk_24h": round(profit_24h, 2),
        "obrot": round(total_staked, 2),
        "yield": round(yield_val, 2),
        "last_sync": now.strftime("%d.%m.%Y %H:%M"),
        "upcoming_val": remaining_count,
        "history_graph": graph_data[-100:]
    }
    with open(STATS_JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(stats_data, f, indent=4)

    wins = sum(1 for m in history if m.get('status') == 'WIN')
    total_matches = sum(1 for m in history if m.get('status') in ['WIN', 'LOSS'])
    accuracy = (wins / total_matches * 100) if total_matches > 0 else 0

    report = [
        "📊 <b>DASHBOARD UPDATED</b>",
        f"🏦 <b>BANKROLL:</b> {round(bankroll, 2)} PLN",
        f"💰 Zysk Total: {round(total_profit, 2)} PLN",
        f"📅 Ostatnie 24h: {round(profit_24h, 2)} PLN",
        f"📈 Yield: {round(yield_val, 2)}% | Celność: {round(accuracy, 1)}%",
        "━━━━━━━━━━━━━━━",
        "📝 <b>OSTATNIE:</b>"
    ]
    for m in reversed(history[-5:]):
        status = "✅" if m.get('status') == 'WIN' else "❌"
        report.append(f"{status} {m.get('home')} - {m.get('away')} ({m.get('profit')} PLN)")

    send_telegram_results("\n".join(report))

def settle_matches():
    api_keys = get_all_api_keys()
    if not os.path.exists(COUPONS_FILE): return
    with open(COUPONS_FILE, "r", encoding="utf-8") as f: active_coupons = json.load(f)
    if not active_coupons: return

    history = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f: history = json.load(f)
        except: pass

    remaining_coupons, new_settlements = [], 0
    results_map = {}
    
    # Automatyczne pobieranie sportów z aktywnych kuponów (już z nowymi nazwami lig)
    sports_to_check = list(set(c['sport'] for c in active_coupons))

    for sport in sports_to_check:
        res = get_match_results(sport, api_keys)
        if res:
            for match in res: results_map[match['id']] = match

    for coupon in active_coupons:
        match_data = results_map.get(coupon['id'])
        if match_data and match_data.get('completed'):
            scores = {s['name']: int(s['score']) for s in match_data.get('scores', [])}
            h_score = scores.get(match_data['home_team'], 0)
            a_score = scores.get(match_data['away_team'], 0)
            
            won = False
            if coupon['outcome'] == match_data['home_team'] and h_score > a_score: won = True
            elif coupon['outcome'] == match_data['away_team'] and a_score > h_score: won = True

            profit = round((float(coupon['stake']) * float(coupon['odds'])) - float(coupon['stake']) if won else -float(coupon['stake']), 2)
            
            history.append({**coupon, "profit": profit, "status": "WIN" if won else "LOSS", "score": f"{h_score}:{a_score}"})
            new_settlements += 1
        else:
            remaining_coupons.append(coupon)

    if new_settlements > 0:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f: json.dump(history, f, indent=4)
        with open(COUPONS_FILE, "w", encoding="utf-8") as f: json.dump(remaining_coupons, f, indent=4)
    
    generate_report(history, len(remaining_coupons))

if __name__ == "__main__":
    settle_matches()
