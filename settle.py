import os
import json
import requests
from datetime import datetime, timezone, timedelta

# --- KONFIGURACJA PLIKÓW ---
COUPONS_FILE = "coupons.json"
HISTORY_FILE = "history.json"

def get_secret(name):
    val = os.environ.get(name) or os.getenv(name)
    return str(val).strip() if val else None

def send_telegram_results(message):
    token = get_secret("T_TOKEN")
    # Szuka specjalnego ID dla wyników, jeśli nie ma - bierze domyślny
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
        url = f"https://api.the-odds-api.com/v4/sports/{sport}/scores/"
        params = {"apiKey": key, "daysFrom": 3}
        try:
            resp = requests.get(url, params=params, timeout=15)
            if resp.status_code == 200: return resp.json()
        except: continue
    return None

def generate_report(history):
    total_profit = sum(m.get('profit', 0) for m in history)
    base_capital = 5000 
    bankroll = base_capital + total_profit
    
    wins = sum(1 for m in history if m.get('status') == 'WIN')
    losses = sum(1 for m in history if m.get('status') == 'LOSS')
    total_matches = wins + losses
    
    accuracy = (wins / total_matches * 100) if total_matches > 0 else 0
    total_staked = sum(m.get('stake', 0) for m in history if m.get('status') in ['WIN', 'LOSS'])
    yield_val = (total_profit / total_staked * 100) if total_staked > 0 else 0

    now = datetime.now(timezone.utc)
    last_24h_profit = sum(m.get('profit', 0) for m in history if (now - datetime.fromisoformat(m['time'].replace("Z", "+00:00"))) < timedelta(hours=24))

    report = [
        "📊 <b>STATYSTYKI</b>",
        "━━━━━━━━━━━━━━━",
        f"🏦 <b>BANKROLL:</b> {round(bankroll, 2)} PLN",
        f"💰 Zysk Total: {round(total_profit, 2)} PLN",
        f"📅 Ostatnie 24h: {'+' if last_24h_profit >=0 else ''}{round(last_24h_profit, 2)} PLN",
        f"🎯 Skuteczność: {round(accuracy, 1)}%",
        f"📈 Yield: {round(yield_val, 2)}%",
        "━━━━━━━━━━━━━━━",
        "📝 <b>OSTATNIE WYNIKI:</b>"
    ]

    for m in reversed(history[-10:]):
        status = "✅" if m['status'] == 'WIN' else "❌" if m['status'] == 'LOSS' else "⚠️"
        score = f" | {m.get('score', '?-?')}"
        profit = f"{'+' if m.get('profit', 0) > 0 else ''}{round(m.get('profit', 0.0), 2)}"
        report.append(f"{status} {m['home']} - {m['away']} | {score} | {profit}")

    report.append("━━━━━━━━━━━━━━━")
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

    remaining_coupons = []
    new_settlements = 0
    now_utc = datetime.now(timezone.utc)
    results_map = {}
    sports_to_check = list(set(c['sport'] for c in active_coupons))

    for sport in sports_to_check:
        res = get_match_results(sport, api_keys)
        if res:
            for match in res: results_map[match['id']] = match

    for coupon in active_coupons:
        match_data = results_map.get(coupon['id'])
        try:
            m_time = datetime.fromisoformat(coupon['time'].replace("Z", "+00:00"))
        except: m_time = now_utc

        if match_data and match_data.get('completed'):
            h_score, a_score = 0, 0
            for s in match_data.get('scores', []):
                if s['name'] == match_data['home_team']: h_score = int(s['score'])
                else: a_score = int(s['score'])

            won = False
            pick = coupon.get('outcome')
            if pick == match_data['home_team'] and h_score > a_score: won = True
            elif pick == match_data['away_team'] and a_score > h_score: won = True

            stake, odds = float(coupon.get('stake', 0)), float(coupon.get('odds', 0))
            profit = round((stake * odds) - stake if won else -stake, 2)

            history.append({
                "id": coupon['id'], "home": coupon['home'], "away": coupon['away'],
                "sport": coupon['sport'], "outcome": pick, "odds": odds, "stake": stake,
                "profit": profit, "status": "WIN" if won else "LOSS", "score": f"{h_score}:{a_score}",
                "time": coupon['time']
            })
            new_settlements += 1
        
        elif (now_utc - m_time) > timedelta(hours=72):
            history.append({
                "id": coupon['id'], "home": coupon['home'], "away": coupon['away'],
                "sport": coupon['sport'], "profit": 0.0, "status": "VOID", "time": coupon['time']
            })
            new_settlements += 1
        else:
            remaining_coupons.append(coupon)

    if new_settlements > 0:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f: json.dump(history, f, indent=4)
        with open(COUPONS_FILE, "w", encoding="utf-8") as f: json.dump(remaining_coupons, f, indent=4)
        generate_report(history)
    else:
        print("Brak nowych wyników do wysłania.")

if __name__ == "__main__":
    settle_matches()
