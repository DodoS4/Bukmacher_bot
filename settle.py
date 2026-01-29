import os
import requests
import json
import time
from datetime import datetime

# ================= KONFIGURACJA =================
COUPONS_FILE = "coupons.json"
HISTORY_FILE = "history.json"
BANKROLL_FILE = "bankroll.json"
KEY_STATE_FILE = "key_index.txt" # Dodano synchronizację kluczy

API_KEYS = []
if os.getenv("ODDS_KEY"): API_KEYS.append(os.getenv("ODDS_KEY"))
for i in range(2, 11):
    key = os.getenv(f"ODDS_KEY_{i}")
    if key and len(key) > 10: API_KEYS.append(key)

def get_current_key_idx():
    if os.path.exists(KEY_STATE_FILE):
        try:
            with open(KEY_STATE_FILE, "r") as f:
                return int(f.read().strip()) % len(API_KEYS)
        except: return 0
    return 0

def save_current_key_idx(idx):
    with open(KEY_STATE_FILE, "w") as f:
        f.write(str(idx))

def settle_matches():
    print(f"🔄 START ROZLICZANIA: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if not os.path.exists(COUPONS_FILE): return
    try:
        with open(COUPONS_FILE, "r", encoding="utf-8") as f:
            coupons = json.load(f)
    except: return
    
    if not coupons:
        print("ℹ️ Brak aktywnych kuponów.")
        return

    history = json.load(open(HISTORY_FILE, "r", encoding="utf-8")) if os.path.exists(HISTORY_FILE) else []
    bankroll_data = json.load(open(BANKROLL_FILE, "r", encoding="utf-8")) if os.path.exists(BANKROLL_FILE) else {"bankroll": 1000.0}
    
    updated_coupons = []
    new_history = []
    leagues = list(set(c['sport'] for c in coupons))
    results_cache = {}
    
    key_idx = get_current_key_idx()

    # KROK 1: Pobieranie wyników (z rotacją kluczy)
    for league in leagues:
        attempts = 0
        while attempts < len(API_KEYS):
            active_key = API_KEYS[key_idx]
            url = f"https://api.the-odds-api.com/v4/sports/{league}/scores/?apiKey={active_key}&daysFrom=3"
            try:
                resp = requests.get(url, timeout=15)
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
    
    save_current_key_idx(key_idx)

    # KROK 2: Analiza wyników
    for bet in coupons:
        league_data = results_cache.get(bet['sport'], [])
        match = next((m for m in league_data if m['id'] == bet['id']), None)
        
        if match and match.get('completed'):
            try:
                scores = match.get('scores', [])
                h_score, a_score = None, None

                if scores:
                    # POPRAWKA: Bardziej elastyczne szukanie drużyn (nie tylko identyczny tekst)
                    h_score_obj = next((s for s in scores if s['name'].lower() in bet['home'].lower() or bet['home'].lower() in s['name'].lower()), None)
                    a_score_obj = next((s for s in scores if s['name'].lower() in bet['away'].lower() or bet['away'].lower() in s['name'].lower()), None)
                    
                    if h_score_obj and a_score_obj:
                        h_score = int(h_score_obj['score'])
                        a_score = int(a_score_obj['score'])
                
                if h_score is not None:
                    bet['score'] = f"{h_score}:{a_score}"
                    
                    if h_score > a_score: actual_winner = bet['home']
                    elif a_score > h_score: actual_winner = bet['away']
                    else: actual_winner = "Draw"

                    # ROZLICZENIE (Zgodne z rynkiem 1X2 - remis to zazwyczaj LOSS dla typu 1 lub 2)
                    if bet['outcome'] == actual_winner:
                        clean_stake = float(bet['stake']) * 0.88
                        bet['profit'] = round((clean_stake * float(bet['odds'])) - float(bet['stake']), 2)
                        bet['status'] = "WIN"
                    elif actual_winner == "Draw" and "nhl" in bet['sport'].lower():
                        # Specyfika NHL (jeśli liczysz z dogrywką - do weryfikacji w API)
                        bet['status'] = "PENDING_OT" 
                        updated_coupons.append(bet)
                        continue
                    else:
                        bet['profit'] = -float(bet['stake'])
                        bet['status'] = "LOSS"

                    bankroll_data["bankroll"] += bet['profit']
                    new_history.append(bet)
                    print(f"✅ {bet['home']} - {bet['away']} | {bet['score']} | {bet['status']}")
                else:
                    updated_coupons.append(bet)
            except Exception as e:
                print(f"⚠️ Błąd przy meczu {bet['id']}: {e}")
                updated_coupons.append(bet)
        else:
            updated_coupons.append(bet)

    # KROK 3: Bezpieczny zapis
    if new_history:
        history.extend(new_history)
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=4)
        
        bankroll_data["bankroll"] = round(bankroll_data["bankroll"], 2)
        with open(BANKROLL_FILE, "w", encoding="utf-8") as f:
            json.dump(bankroll_data, f, indent=4)
    
    with open(COUPONS_FILE, "w", encoding="utf-8") as f:
        json.dump(updated_coupons, f, indent=4)
    
    print(f"🏁 Rozliczono: {len(new_history)} | Aktywne: {len(updated_coupons)}")

if __name__ == "__main__":
    settle_matches()
