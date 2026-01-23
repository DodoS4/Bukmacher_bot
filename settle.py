import os
import requests
import json
from datetime import datetime

# ================= KONFIGURACJA =================
COUPONS_FILE = "coupons.json"
HISTORY_FILE = "history.json"
BANKROLL_FILE = "bankroll.json"

# Obsługa 10 kluczy API
API_KEYS = []
if os.getenv("ODDS_KEY"): API_KEYS.append(os.getenv("ODDS_KEY"))
for i in range(2, 11):
    key = os.getenv(f"ODDS_KEY_{i}")
    if key and len(key) > 10:
        API_KEYS.append(key)

def settle_matches():
    print(f"🔄 START ROZLICZANIA: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if not os.path.exists(COUPONS_FILE):
        print("ℹ️ Brak pliku kuponów.")
        return
        
    try:
        with open(COUPONS_FILE, "r", encoding="utf-8") as f:
            coupons = json.load(f)
    except:
        return
    
    if not coupons:
        print("ℹ️ Brak aktywnych kuponów.")
        return

    history = json.load(open(HISTORY_FILE, "r", encoding="utf-8")) if os.path.exists(HISTORY_FILE) else []
    bankroll_data = json.load(open(BANKROLL_FILE, "r", encoding="utf-8")) if os.path.exists(BANKROLL_FILE) else {"bankroll": 1000.0}
    
    updated_coupons = []
    new_history = []
    leagues = list(set(c['sport'] for c in coupons))
    results_cache = {}
    
    # KROK 1: Pobieranie wyników
    key_idx = 0
    for league in leagues:
        success = False
        attempts = 0
        while attempts < len(API_KEYS):
            active_key = API_KEYS[key_idx]
            url = f"https://api.the-odds-api.com/v4/sports/{league}/scores/?apiKey={active_key}&daysFrom=3"
            try:
                resp = requests.get(url, timeout=15)
                if resp.status_code == 200:
                    results_cache[league] = resp.json()
                    success = True
                    break
                elif resp.status_code in [401, 429]:
                    key_idx = (key_idx + 1) % len(API_KEYS)
                    attempts += 1
                else:
                    break
            except:
                key_idx = (key_idx + 1) % len(API_KEYS)
                attempts += 1
    
    # KROK 2: Analiza wyników
    for bet in coupons:
        league_data = results_cache.get(bet['sport'], [])
        match = next((m for m in league_data if m['id'] == bet['id']), None)
        
        if match and match.get('completed'):
            try:
                scores = match.get('scores', [])
                h_score, a_score = None, None

                if scores:
                    h_score_obj = next((s for s in scores if s['name'] == bet['home']), None)
                    a_score_obj = next((s for s in scores if s['name'] == bet['away']), None)
                    if h_score_obj and a_score_obj:
                        h_score = int(h_score_obj['score'])
                        a_score = int(a_score_obj['score'])
                
                if h_score is not None:
                    bet['score'] = f"{h_score}:{a_score}"
                    
                    if h_score > a_score: actual_winner = bet['home']
                    elif a_score > h_score: actual_winner = bet['away']
                    else: actual_winner = "Draw"

                    # ROZLICZENIE
                    if bet['outcome'] == actual_winner:
                        # WYGRANA: (Stawka * 0.88 * Kurs) - Stawka
                        clean_stake = float(bet['stake']) * 0.88
                        bet['profit'] = round((clean_stake * float(bet['odds'])) - float(bet['stake']), 2)
                        bet['status'] = "WIN"
                    elif actual_winner == "Draw" and bet['outcome'] not in [bet['home'], bet['away'], "Draw"]:
                        # ZWROT (np. jeśli system postawił coś innego a był remis - do decyzji)
                        bet['profit'] = 0.0
                        bet['status'] = "VOID"
                    else:
                        # PRZEGRANA
                        bet['profit'] = -float(bet['stake'])
                        bet['status'] = "LOSS"

                    bankroll_data["bankroll"] += bet['profit']
                    new_history.append(bet)
                    print(f"✅ {bet['home']} - {bet['away']} | {bet['score']} | {bet['status']} ({bet['profit']} PLN)")
                else:
                    updated_coupons.append(bet)
            except:
                updated_coupons.append(bet)
        else:
            updated_coupons.append(bet)

    # KROK 3: Zapis danych
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
