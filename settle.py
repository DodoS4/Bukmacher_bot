import json
import os
import requests

ODDS_API_KEY = os.getenv("ODDS_KEY")
HISTORY_FILE = "history.json"
COUPONS_FILE = "coupons.json"
BANKROLL_FILE = "bankroll.json"
TELEGRAM_TOKEN = os.getenv("T_TOKEN")
TELEGRAM_CHAT = os.getenv("T_CHAT_RESULTS")

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": TELEGRAM_CHAT, "text": message, "parse_mode": "HTML"})

def settle_matches():
    if not os.path.exists(COUPONS_FILE): return
    with open(COUPONS_FILE, "r") as f: coupons = json.load(f)
    if not os.path.exists(BANKROLL_FILE): json.dump({"bankroll": 1000.0}, open(BANKROLL_FILE, "w"))
    with open(BANKROLL_FILE, "r") as f: br_data = json.load(f)
    if not os.path.exists(HISTORY_FILE): json.dump([], open(HISTORY_FILE, "w"))
    with open(HISTORY_FILE, "r") as f: history = json.load(f)

    remaining = []
    for c in coupons:
        url = f"https://api.the-odds-api.com/v4/sports/{c['sport']}/scores/?apiKey={ODDS_API_KEY}&daysFrom=3"
        scores_data = requests.get(url).json()
        match = next((m for m in scores_data if m['id'] == c['id'] and m['completed']), None)
        
        if match:
            h_score = int(next(s['score'] for s in match['scores'] if s['name'] == c['home']))
            a_score = int(next(s['score'] for s in match['scores'] if s['name'] == c['away']))
            
            win = False
            if c['pick'] == c['home'] and h_score > a_score: win = True
            elif c['pick'] == c['away'] and a_score > h_score: win = True
            elif c['pick'] == "Draw" and h_score == a_score: win = True

            profit = (c['stake'] * c['odds'] - c['stake']) if win else -c['stake']
            br_data['bankroll'] += profit
            history.append({"date": c['time'], "match": f"{c['home']}-{c['away']}", "sport": c['sport'], "profit": round(profit, 2), "win": win, "odds": c['odds']})
            
            send_telegram(f"{'✅' if win else '❌'} {c['home']}-{c['away']} ({h_score}:{a_score})\nProfit: {profit:+.2f} PLN")
        else:
            remaining.append(c)

    json.dump(remaining, open(COUPONS_FILE, "w"))
    json.dump(history, open(HISTORY_FILE, "w"))
    json.dump(br_data, open(BANKROLL_FILE, "w"))

if __name__ == "__main__":
    settle_matches()
