import os
import requests
import json

# ================= KONFIGURACJA =================
COUPONS_FILE = "coupons.json"
HISTORY_FILE = "history.json"
BANKROLL_FILE = "bankroll.json"

KEYS = [os.getenv(k) for k in ["ODDS_KEY", "ODDS_KEY_2", "ODDS_KEY_3", "ODDS_KEY_4", "ODDS_KEY_5"]]
API_KEYS = [k for k in KEYS if k]

def settle_matches():
    if not os.path.exists(COUPONS_FILE): return
    try:
        coupons = json.load(open(COUPONS_FILE, "r", encoding="utf-8"))
    except: return
    
    if not coupons: return

    history = json.load(open(HISTORY_FILE, "r", encoding="utf-8")) if os.path.exists(HISTORY_FILE) else []
    bankroll_data = json.load(open(BANKROLL_FILE, "r", encoding="utf-8")) if os.path.exists(BANKROLL_FILE) else {"bankroll": 1000.0}
    
    updated_coupons = []
    new_history = []
    leagues = list(set(c['sport'] for c in coupons))
    results_cache = {}
    
    key_idx = 0
    for league in leagues:
        success = False
        while key_idx < len(API_KEYS):
            url = f"https://api.the-odds-api.com/v4/sports/{league}/scores/?apiKey={API_KEYS[key_idx]}&daysFrom=3"
            try:
                resp = requests.get(url)
                if resp.status_code == 200:
                    results_cache[league] = resp.json()
                    success = True
                    break
                key_idx += 1
            except:
                key_idx += 1
    
    for bet in coupons:
        league_data = results_cache.get(bet['sport'], [])
        match = next((m for m in league_data if m['id'] == bet['id']), None)
        
        if match and match.get('completed'):
            try:
                scores = match.get('scores', [])
                h_score, a_score = None, None

                if len(scores) >= 2:
                    # 1. Próba dopasowania po nazwie
                    h_score_data = next((s for s in scores if s['name'] == bet['home']), None)
                    a_score_data = next((s for s in scores if s['name'] == bet['away']), None)
                    
                    if h_score_data and a_score_data:
                        h_score = int(h_score_data['score'])
                        a_score = int(a_score_data['score'])
                    else:
                        # 2. Rezerwowe dopasowanie po kolejności (częste w hokeju)
                        h_score = int(scores[0]['score'])
                        a_score = int(scores[1]['score'])

                if h_score is not None:
                    bet['score'] = f"{h_score}:{a_score}"
                    
                    # Logika wygranej
                    winner = "Draw"
                    if h_score > a_score: winner = bet['home']
                    elif a_score > h_score: winner = bet['away']

                    if bet['outcome'] == winner:
                        bet['profit'] = round((bet['stake'] * bet['odds'] * 0.88) - bet['stake'], 2)
                    else:
                        bet['profit'] = -float(bet['stake'])

                    bankroll_data["bankroll"] += bet['profit']
                    new_history.append(bet)
                else:
                    updated_coupons.append(bet)
            except Exception as e:
                updated_coupons.append(bet)
        else:
            updated_coupons.append(bet)

    if new_history:
        history.extend(new_history)
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=4)
        bankroll_data["bankroll"] = round(bankroll_data["bankroll"], 2)
        with open(BANKROLL_FILE, "w", encoding="utf-8") as f:
            json.dump(bankroll_data, f, indent=4)
    
    with open(COUPONS_FILE, "w", encoding="utf-8") as f:
        json.dump(updated_coupons, f, indent=4)

if __name__ == "__main__":
    settle_matches()
