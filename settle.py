import os
import requests
import json

# ================= KONFIGURACJA =================
COUPONS_FILE = "coupons.json"
HISTORY_FILE = "history.json"
BANKROLL_FILE = "bankroll.json"

# Pobieramy wszystkie klucze z GitHub Secrets
KEYS = [os.getenv(k) for k in ["ODDS_KEY", "ODDS_KEY_2", "ODDS_KEY_3", "ODDS_KEY_4", "ODDS_KEY_5"]]
API_KEYS = [k for k in KEYS if k] # Filtrujemy tylko te, które nie są puste

def settle_matches():
    if not os.path.exists(COUPONS_FILE):
        print("Brak pliku kuponów.")
        return

    coupons = json.load(open(COUPONS_FILE, "r", encoding="utf-8"))
    if not coupons:
        print("Brak aktywnych kuponów.")
        return

    history = json.load(open(HISTORY_FILE, "r", encoding="utf-8")) if os.path.exists(HISTORY_FILE) else []
    bankroll_data = json.load(open(BANKROLL_FILE, "r", encoding="utf-8")) if os.path.exists(BANKROLL_FILE) else {"bankroll": 1000.0}
    
    updated_coupons = []
    new_history = []
    
    # Grupujemy ligi, by oszczędzać zapytania
    leagues = list(set(c['sport'] for c in coupons))
    results_cache = {}
    
    key_idx = 0
    for league in leagues:
        success = False
        while key_idx < len(API_KEYS):
            current_key = API_KEYS[key_idx]
            url = f"https://api.the-odds-api.com/v4/sports/{league}/scores/?apiKey={current_key}&daysFrom=3"
            
            try:
                resp = requests.get(url)
                if resp.status_code == 200:
                    results_cache[league] = resp.json()
                    success = True
                    break
                else:
                    print(f"Błąd klucza {key_idx}: {resp.status_code}. Próbuję następny...")
                    key_idx += 1
            except:
                key_idx += 1
        
        if not success:
            print(f"Nie udało się pobrać wyników dla ligi: {league}")

    for bet in coupons:
        league_data = results_cache.get(bet['sport'], [])
        match = next((m for m in league_data if m['id'] == bet['id']), None)
        
        if match and match.get('completed'):
            try:
                scores = match['scores']
                # Próba dopasowania wyników po nazwie drużyny
                h_score = next(int(s['score']) for s in scores if s['name'] == bet['home'])
                a_score = next(int(s['score']) for s in scores if s['name'] == bet['away'])
                
                bet['score'] = f"{h_score}:{a_score}"
                
                # Logika rozliczenia
                winner = "Draw"
                if h_score > a_score: winner = bet['home']
                elif a_score > h_score: winner = bet['away']

                if bet['outcome'] == winner:
                    bet['profit'] = round((bet['stake'] * bet['odds'] * 0.88) - bet['stake'], 2)
                else:
                    bet['profit'] = -float(bet['stake'])

                bankroll_data["bankroll"] += bet['profit']
                new_history.append(bet)
                print(f"Rozliczono: {bet['home']} - {bet['away']} ({bet['score']}) -> {bet['profit']} PLN")
            except Exception as e:
                print(f"Błąd przetwarzania wyniku dla {bet['id']}: {e}")
                updated_coupons.append(bet)
        else:
            updated_coupons.append(bet)

    # Zapis danych
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
