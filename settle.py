import os
import json
import requests

COUPONS_FILE = "coupons.json"
HISTORY_FILE = "history.json"
API_KEY = os.getenv("ODDS_KEY")

def settle_matches():
    if not os.path.exists(COUPONS_FILE): return
    with open(COUPONS_FILE, "r") as f: active = json.load(f)
    if not active: return

    history = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f: history = json.load(f)

    remaining, new_s = [], 0
    for c in active:
        url = f"https://api.the-odds-api.com/v4/sports/{c['sport']}/scores/?apiKey={API_KEY}&daysFrom=3"
        try:
            data = requests.get(url, timeout=10).json()
            match = next((m for m in data if m['id'] == c['id']), None)
            
            if match and match.get('completed'):
                scores = {s['name']: int(s['score']) for s in match.get('scores', [])}
                h_score = scores.get(match['home_team'], 0)
                a_score = scores.get(match['away_team'], 0)
                
                won = (c['outcome'] == match['home_team'] and h_score > a_score) or \
                      (c['outcome'] == match['away_team'] and a_score > h_score)
                
                profit = (c['stake'] * c['odds'] - c['stake']) if won else -c['stake']
                history.append({**c, "profit": round(profit, 2), "status": "WIN" if won else "LOSS", "score": f"{h_score}:{a_score}"})
                new_s += 1
            else: remaining.append(c)
        except: remaining.append(c)

    if new_s > 0:
        with open(HISTORY_FILE, "w") as f: json.dump(history, f, indent=4)
        with open(COUPONS_FILE, "w") as f: json.dump(remaining, f, indent=4)
        print(f"✅ Rozliczono: {new_s}")

if __name__ == "__main__":
    settle_matches()
