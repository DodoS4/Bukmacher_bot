import os
import requests
import json
from datetime import datetime

# ================= KONFIGURACJA =================
COUPONS_FILE = "coupons.json"
HISTORY_FILE = "history.json"
BANKROLL_FILE = "bankroll.json"

API_KEYS = []
if os.getenv("ODDS_KEY"): API_KEYS.append(os.getenv("ODDS_KEY"))
for i in range(2, 11):
    key = os.getenv(f"ODDS_KEY_{i}")
    if key and len(key) > 10: API_KEYS.append(key)

def settle_matches():
    print(f"🔄 START ROZLICZANIA: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if not os.path.exists(COUPONS_FILE): return
    try:
        with open(COUPONS_FILE, "r", encoding="utf-8") as f:
            coupons = json.load(f)
    except: return
    
    if not coupons: return

    history = json.load(open(HISTORY_FILE, "r", encoding="utf-8")) if os.path.exists(HISTORY_FILE) else []
    bankroll_data = json.load(open(BANKROLL_FILE, "r", encoding="utf-8")) if os.path.exists(BANKROLL_FILE) else {"bankroll": 1000.0}
    
    updated_coupons = []
    new_history = []
    leagues = list(set(c['sport'] for c in coupons))
    results_cache = {}
    
    # ROTACJA KLUCZY
    key_idx = 0
    for league in leagues:
        attempts = 0
        while attempts < len(API_KEYS):
            active_key = API_KEYS[key_idx]
            url = f"https://api.the-odds-api.com/v4/sports/{league}/scores/?apiKey={active_key}&daysFrom=3"
            try:
                resp = requests.get(url, timeout=20) # DODANY TIMEOUT
                if resp.status_code == 200:
                    results_cache[league] = resp.json()
                    break
                elif resp.status_code in [401, 429]:
                    key_idx = (key_idx + 1) % len(API_KEYS)
                    attempts += 1
                else: break
            except:
                key_idx = (key_idx + 1) % len(API_KEYS)
                attempts += 1
    
    for bet in coupons:
        league_data = results_cache.get(bet['sport'], [])
        match = next((m for m in league_data if m['id'] == bet['id']), None)
        
        # DODANY WARUNEK: Sprawdzenie czy scores istnieją
        if match and match.get('completed') and match.get('scores'):
            try:
                scores = match['scores']
                h_score = next((int(s['score']) for s in scores if s['name'] == bet['home']), None)
                a_score = next((int(s['score']) for s in scores if s['name'] == bet['away']), None)
                
                if h_score is not None and a_score is not None:
                    bet['score'] = f"{h_score}:{a_score}"
                    
                    # Logika zwycięzcy (NHL ML / Soccer H2H)
                    actual_winner = bet['home'] if h_score > a_score else (bet['away'] if a_score > h_score else "Draw")

                    if bet['outcome'] == actual_winner:
                        clean_stake = float(bet['stake']) * 0.88
                        bet['profit'] = round((clean_stake * float(bet['odds'])) - float(bet['stake']), 2)
                        bet['status'] = "WIN"
                    else:
                        bet['profit'] = -float(bet['stake'])
                        bet['status'] = "LOSS"

                    bankroll_data["bankroll"] += bet['profit']
                    new_history.append(bet)
                else: updated_coupons.append(bet)
            except: updated_coupons.append(bet)
        else: updated_coupons.append(bet)

    # ZAPIS
    if new_history:
        history.extend(new_history)
        with open(HISTORY_FILE, "w", encoding="utf-8") as f: json.dump(history, f, indent=4)
        bankroll_data["bankroll"] = round(bankroll_data["bankroll"], 2)
        with open(BANKROLL_FILE, "w", encoding="utf-8") as f: json.dump(bankroll_data, f, indent=4)
    
    with open(COUPONS_FILE, "w", encoding="utf-8") as f: json.dump(updated_coupons, f, indent=4)
    print(f"🏁 Rozliczono: {len(new_history)}")

if __name__ == "__main__":
    settle_matches()
