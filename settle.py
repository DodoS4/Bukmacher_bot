import os
import requests
import json
from datetime import datetime

# ================= KONFIGURACJA =================
COUPONS_FILE = "coupons.json"
HISTORY_FILE = "history.json"
BANKROLL_FILE = "bankroll.json"
API_KEYS = [os.getenv(f"ODDS_KEY{i}") for i in ["", "_2", "_3", "_4", "_5"]]

def load_json(file, default):
    if os.path.exists(file):
        with open(file, "r", encoding="utf-8") as f:
            try: return json.load(f)
            except: return default
    return default

def save_json(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def settle_matches():
    coupons = load_json(COUPONS_FILE, [])
    history = load_json(HISTORY_FILE, [])
    bankroll_data = load_json(BANKROLL_FILE, {"bankroll": 1000.0})
    
    if not coupons:
        return

    updated_coupons = []
    new_history_entries = []
    current_bankroll = bankroll_data["bankroll"]

    # Używamy pierwszego dostępnego klucza API
    api_key = next((k for k in API_KEYS if k), None)

    for bet in coupons:
        # Sprawdzamy wyniki (scores) dla danej ligi
        url = f"https://api.the-odds-api.com/v4/sports/{bet['sport']}/scores/"
        params = {"apiKey": api_key, "daysFrom": 3}
        
        try:
            resp = requests.get(url, params=params)
            results = resp.json()
            
            # Szukamy konkretnego meczu w wynikach
            match_result = next((m for m in results if m['id'] == bet['id']), None)

            if match_result and match_result.get('completed'):
                # Wyciągamy wynik końcowy
                home_score = next((s['score'] for s in match_result['scores'] if s['name'] == bet['home']), 0)
                away_score = next((s['score'] for s in match_result['scores'] if s['name'] == bet['away']), 0)
                
                home_score = int(home_score)
                away_score = int(away_score)

                # Określamy zwycięzcę
                winner = "Draw"
                if home_score > away_score: winner = bet['home']
                elif away_score > home_score: winner = bet['away']

                # Rozliczamy kupon
                if bet['outcome'] == winner:
                    # Wygrana: (Stawka * Kurs * 0.88) - Stawka
                    # Używamy round(), aby uniknąć błędów w groszach
                    raw_profit = (bet['stake'] * bet['odds'] * 0.88) - bet['stake']
                    bet['profit'] = round(raw_profit, 2)
                else:
                    # Przegrana: tracimy stawkę
                    bet['profit'] = -float(bet['stake'])

                current_bankroll += bet['profit']
                new_history_entries.append(bet)
            else:
                # Mecz jeszcze trwa lub nie ma wyników - zostaje w coupons.json
                updated_coupons.append(bet)

        except Exception as e:
            print(f"Błąd rozliczania meczu {bet['id']}: {e}")
            updated_coupons.append(bet)

    # Zapisujemy zmiany
    if new_history_entries:
        history.extend(new_history_entries)
        save_json(HISTORY_FILE, history)
        
        bankroll_data["bankroll"] = round(current_bankroll, 2)
        save_json(BANKROLL_FILE, bankroll_data)
        
    save_json(COUPONS_FILE, updated_coupons)
    print(f"Rozliczono {len(new_history_entries)} meczów. Aktualny bankroll: {bankroll_data['bankroll']}")

if __name__ == "__main__":
    settle_matches()
