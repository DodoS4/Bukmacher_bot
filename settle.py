import os
import json
import requests
from datetime import datetime, timezone, timedelta

# --- KONFIGURACJA ---
COUPONS_FILE = "coupons.json"
HISTORY_FILE = "history.json"
STATS_JSON_FILE = "stats.json"

def get_secret(name):
    val = os.environ.get(name) or os.getenv(name)
    return str(val).strip() if val else None

def update_web_stats(history, bankroll, total_profit, accuracy, yield_val):
    """Aktualizuje plik stats.json dla strony WWW"""
    stats_data = {
        "bankroll": round(bankroll, 2),
        "total_profit": round(total_profit, 2),
        "accuracy": round(accuracy, 1),
        "yield": round(yield_val, 2),
        "last_update": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "history_preview": history[-15:]
    }
    with open(STATS_JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(stats_data, f, indent=4)
    print("✅ Strona WWW zaktualizowana.")

def send_telegram_results(message):
    token = get_secret("T_TOKEN")
    chat = get_secret("T_CHAT_RESULTS") or get_secret("T_CHAT")
    if not token or not chat: return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat, "text": message, "parse_mode": "HTML"}
    try: requests.post(url, json=payload, timeout=15)
    except: pass

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

    # Wysyłka na Telegram
    report = [
        "📊 <b>STATYSTYKI</b>",
        f"🏦 <b>BANKROLL:</b> {round(bankroll, 2)} PLN",
        f"💰 Zysk Total: {round(total_profit, 2)} PLN",
        f"🎯 Skuteczność: {round(accuracy, 1)}% | Yield: {round(yield_val, 2)}%",
        "━━━━━━━━━━━━━━━",
        "📝 <b>OSTATNIE WYNIKI:</b>"
    ]
    for m in reversed(history[-10:]):
        status = "✅" if m['status'] == 'WIN' else "❌" if m['status'] == 'LOSS' else "⚠️"
        report.append(f"{status} {m['home']} - {m['away']} | {m.get('score', '?-?')} | {m.get('profit', 0)}")
    
    send_telegram_results("\n".join(report))
    # Aktualizacja strony WWW
    update_web_stats(history, bankroll, total_profit, accuracy, yield_val)

def get_match_results(sport, keys):
    for key in keys:
        url = f"https://api.the-odds-api.com/v4/sports/{sport}/scores/"
        params = {"apiKey": key, "daysFrom": 3}
        try:
            resp = requests.get(url, params=params, timeout=15)
            if resp.status_code == 200: return resp.json()
        except: continue
    return None

def settle_matches():
    api_keys = [get_secret(f"ODDS_KEY_{i}" if i > 1 else "ODDS_KEY") for i in range(1, 11) if get_secret(f"ODDS_KEY_{i}" if i > 1 else "ODDS_KEY")]
    if not os.path.exists(COUPONS_FILE): return
    with open(COUPONS_FILE, "r", encoding="utf-8") as f: active_coupons = json.load(f)
    if not active_coupons: return

    history = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f: history = json.load(f)

    results_map = {}
    for sport in set(c['sport'] for c in active_coupons):
        res = get_match_results(sport, api_keys)
        if res:
            for match in res: results_map[match['id']] = match

    new_settlements, remaining = 0, []
    for coupon in active_coupons:
        match_data = results_map.get(coupon['id'])
        if match_data and match_data.get('completed'):
            h_score = next((s['score'] for s in match_data['scores'] if s['name'] == match_data['home_team']), 0)
            a_score = next((s['score'] for s in match_data['scores'] if s['name'] != match_data['home_team']), 0)
            
            won = (coupon['outcome'] == match_data['home_team'] and int(h_score) > int(a_score)) or \
                  (coupon['outcome'] == match_data['away_team'] and int(a_score) > int(h_score))
            
            profit = round((float(coupon['stake']) * float(coupon['odds'])) - float(coupon['stake']) if won else -float(coupon['stake']), 2)
            history.append({**coupon, "profit": profit, "status": "WIN" if won else "LOSS", "score": f"{h_score}:{a_score}"})
            new_settlements += 1
        else: remaining.append(coupon)

    if new_settlements > 0:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f: json.dump(history, f, indent=4)
        with open(COUPONS_FILE, "w", encoding="utf-8") as f: json.dump(remaining, f, indent=4)
        generate_report(history)
    else:
        # Nawet jak nie ma wyników, odśwież raport/stronę na podstawie starej historii
        generate_report(history)

if __name__ == "__main__":
    settle_matches()
