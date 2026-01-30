import os
import json
import requests
from datetime import datetime

COUPONS_FILE = "coupons.json"
HISTORY_FILE = "history.json"
BANKROLL_FILE = "bankroll.json"
API_KEY = os.getenv("ODDS_KEY_1") or os.getenv("ODDS_KEY")

def update_bankroll(amount):
    balance = 100.0
    if os.path.exists(BANKROLL_FILE):
        with open(BANKROLL_FILE, "r") as f:
            data = json.load(f)
            balance = data.get("balance", 100.0)
    
    new_balance = round(balance + amount, 2)
    with open(BANKROLL_FILE, "w") as f:
        json.dump({"balance": new_balance}, f)
    return new_balance

def settle_bets():
    if not os.path.exists(COUPONS_FILE): return
    with open(COUPONS_FILE, "r") as f:
        coupons = json.load(f)
    if not coupons: return

    remaining_coupons = []
    history = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            try: history = json.load(f)
            except: history = []

    for c in coupons:
        sport = c['sport']
        url = f"https://api.the-odds-api.com/v4/sports/{sport}/scores/"
        params = {"apiKey": API_KEY, "daysFrom": 3}
        
        try:
            resp = requests.get(url, params=params)
            if resp.status_code != 200:
                remaining_coupons.append(c)
                continue
            
            scores = resp.json()
            match_result = next((m for m in scores if m['id'] == c['id']), None)

            if match_result and match_result.get('completed'):
                home_score = 0
                away_score = 0
                for s in match_result.get('scores', []):
                    if s['name'] == match_result['home_team']: home_score = int(s['score'])
                    if s['name'] == match_result['away_team']: away_score = int(s['score'])

                won = False
                if c['outcome'] == match_result['home_team'] and home_score > away_score: won = True
                elif c['outcome'] == match_result['away_team'] and away_score > home_score: won = True
                elif c['outcome'] == "Draw" and home_score == away_score: won = True

                # --- LOGIKA PODATKOWA 12% ---
                if won:
                    # Wygrana = (Stawka * 0.88) * Kurs
                    win_amount = (c['stake'] * 0.88) * c['odds']
                    profit = round(win_amount - c['stake'], 2)
                else:
                    profit = -c['stake']
                
                new_bal = update_bankroll(profit)
                
                c['status'] = "WON" if won else "LOST"
                c['score'] = f"{home_score}:{away_score}"
                c['profit'] = profit
                history.append(c)
            else:
                remaining_coupons.append(c)
        except:
            remaining_coupons.append(c)

    with open(COUPONS_FILE, "w") as f:
        json.dump(remaining_coupons, f, indent=4)
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=4)

if __name__ == "__main__":
    settle_bets()
