import os
import requests
import json
from datetime import datetime

# ================= KONFIGURACJA =================
COUPONS_FILE = "coupons.json"
HISTORY_FILE = "history.json"
BANKROLL_FILE = "bankroll.json"

KEYS_RAW = [os.getenv(f"ODDS_KEY{i}") for i in ["", "_2", "_3", "_4", "_5"]]
API_KEYS = [k for k in KEYS_RAW if k and len(k) > 10]

def settle_matches():
    print(f"🔄 START ROZLICZANIA: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if not os.path.exists(COUPONS_FILE):
        print("ℹ️ Brak pliku kuponów do rozliczenia.")
        return
        
    try:
        with open(COUPONS_FILE, "r", encoding="utf-8") as f:
            coupons = json.load(f)
    except Exception as e:
        print(f"❌ Błąd odczytu kuponów: {e}")
        return
    
    if not coupons:
        print("ℹ️ Brak aktywnych kuponów.")
        return

    # Ładowanie historii i bankrolla
    history = json.load(open(HISTORY_FILE, "r", encoding="utf-8")) if os.path.exists(HISTORY_FILE) else []
    
    # Inicjalizacja bankrolla jeśli nie istnieje (zaczynamy od 1000 PLN + Twój obecny zysk)
    if os.path.exists(BANKROLL_FILE):
        bankroll_data = json.load(open(BANKROLL_FILE, "r", encoding="utf-8"))
    else:
        bankroll_data = {"bankroll": 1000.0} 
    
    updated_coupons = []
    new_history = []
    # Pobieramy unikalne klucze lig z aktywnych kuponów
    leagues = list(set(c['sport'] for c in coupons))
    results_cache = {}
    
    # KROK 1: Pobieranie wyników (z obsługą wielu kluczy)
    key_idx = 0
    for league in leagues:
        success = False
        while key_idx < len(API_KEYS):
            # Używamy endpointu /scores/
            url = f"https://api.the-odds-api.com/v4/sports/{league}/scores/?apiKey={API_KEYS[key_idx]}&daysFrom=3"
            try:
                resp = requests.get(url, timeout=15)
                if resp.status_code == 200:
                    results_cache[league] = resp.json()
                    success = True
                    break
                elif resp.status_code in [401, 429]:
                    print(f"⚠️ Klucz {key_idx} wyczerpany. Przełączam...")
                    key_idx += 1
                else:
                    break
            except Exception as e:
                print(f"💥 Błąd połączenia dla {league}: {e}")
                key_idx += 1
    
    # KROK 2: Analiza wyników
    for bet in coupons:
        league_data = results_cache.get(bet['sport'], [])
        match = next((m for m in league_data if m['id'] == bet['id']), None)
        
        # Rozliczamy tylko jeśli API potwierdza zakończenie meczu
        if match and match.get('completed'):
            try:
                scores = match.get('scores', [])
                h_score, a_score = None, None

                if scores and len(scores) >= 2:
                    # Szukanie wyniku po nazwie drużyny (najbezpieczniejsza metoda)
                    h_score_obj = next((s for s in scores if s['name'] == bet['home']), None)
                    a_score_obj = next((s for s in scores if s['name'] == bet['away']), None)
                    
                    if h_score_obj and a_score_obj:
                        h_score = int(h_score_obj['score'])
                        a_score = int(a_score_obj['score'])
                
                if h_score is not None:
                    bet['score'] = f"{h_score}:{a_score}"
                    
                    # Logika zwycięstwa
                    if h_score > a_score:
                        actual_winner = bet['home']
                    elif a_score > h_score:
                        actual_winner = bet['away']
                    else:
                        actual_winner = "Draw"

                    # Rozliczenie (Polska: podatek 12%)
                    if bet['outcome'] == actual_winner:
                        # Wygrana: (Stawka * 0.88 * Kurs) - Stawka
                        # Używamy 0.88, ponieważ podatek 12% pobierany jest od stawki wejściowej
                        clean_stake = float(bet['stake']) * 0.88
                        bet['profit'] = round((clean_stake * float(bet['odds'])) - float(bet['stake']), 2)
                        bet['status'] = "WIN"
                    else:
                        # Przegrana: Tracimy całą postawioną stawkę
                        bet['profit'] = -float(bet['stake'])
                        bet['status'] = "LOSS"

                    bankroll_data["bankroll"] += bet['profit']
                    new_history.append(bet)
                    print(f"✅ {bet['home']} - {bet['away']} | {bet['score']} | {bet['status']} ({bet['profit']} PLN)")
                else:
                    updated_coupons.append(bet)
            except Exception as e:
                print(f"⚠️ Problem z meczem {bet['id']}: {e}")
                updated_coupons.append(bet)
        else:
            # Jeśli meczu nie ma w wynikach lub jeszcze trwa, zostaje w kuponach
            updated_coupons.append(bet)

    # KROK 3: Zapisywanie
    if new_history:
        history.extend(new_history)
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=4)
        
        bankroll_data["bankroll"] = round(bankroll_data["bankroll"], 2)
        with open(BANKROLL_FILE, "w", encoding="utf-8") as f:
            json.dump(bankroll_data, f, indent=4)
    
    with open(COUPONS_FILE, "w", encoding="utf-8") as f:
        json.dump(updated_coupons, f, indent=4)
    
    print(f"🏁 KONIEC. Rozliczono: {len(new_history)} | Pozostało: {len(updated_coupons)}")

if __name__ == "__main__":
    settle_matches()
