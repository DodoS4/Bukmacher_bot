import os
import requests
import json
from datetime import datetime

# ================= KONFIGURACJA =================
COUPONS_FILE = "coupons.json"
HISTORY_FILE = "history.json"
BANKROLL_FILE = "bankroll.json"
# Pobieranie kluczy z GitHub Secrets
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
        print("Brak kuponów do rozliczenia.")
        return

    updated_coupons = []
    new_history_entries = []
    current_bankroll = bankroll_data["bankroll"]

    # Używamy pierwszego dostępnego klucza API
    api_key = next((k for k in API_KEYS if k), None)
    if not api_key:
        print("Błąd: Brak klucza API!")
        return

    for bet in coupons:
        # Sprawdzamy wyniki (scores) dla danej ligi
        url = f"https://api.the-odds-api.com/v4/sports/{bet['sport']}/scores/"
        params = {"apiKey": api_key, "daysFrom": 3}
        
        try:
            resp = requests.get(url, params=params)
            # Jeśli przekroczono limit API, przejdź do następnego meczu
            if resp.status_code != 200:
                print(f"API Error {resp.status_code} dla ligi {bet['sport']}")
                updated_coupons.append(bet)
                continue

            results = resp.json()
            
            # Szukamy konkretnego meczu w wynikach po ID
            match_result = next((m for m in results if m['id'] == bet['id']), None)

            if match_result and match_result.get('completed'):
                # Wyciągamy punkty/bramki
                # Szukamy nazwy drużyny w wynikach API
                h_data = next((s for s in match_result['scores'] if s['name'] == bet['home']), None)
                a_data = next((s for s in match_result['scores'] if s['name'] == bet['away']), None)
                
                if h_data is not None and a_data is not None:
                    home_score = int(h_data['score'])
                    away_score = int(a_data['score'])
                    
                    # --- KLUCZOWA POPRAWKA DLA DASHBOARDU ---
                    # Zapisujemy wynik do obiektu zakładu, który trafi do historii
                    bet['score'] = f"{home_score}:{away_score}"
                    # -----------------------------------------

                    # Określamy zwycięzcę (Winner)
                    winner = "Draw"
                    if home_score > away_score: winner = bet['home']
                    elif away_score > home_score: winner = bet['away']

                    # Rozliczamy finansowo
                    if bet['outcome'] == winner:
                        # Wygrana: (Stawka * Kurs * 0.88) - Stawka
                        raw_profit = (bet['stake'] * bet['odds'] * 0.88) - bet['stake']
                        bet['profit'] = round(raw_profit, 2)
                    else:
                        # Przegrana: tracimy całą stawkę
                        bet['profit'] = -float(bet['stake'])

                    current_bankroll += bet['profit']
                    new_history_entries.append(bet)
                else:
                    # Jeśli nie znaleziono punktów, zostawiamy w kuponach
                    updated_coupons.append(bet)
            else:
                # Mecz jeszcze trwa lub API nie zwróciło statusu 'completed'
                updated_coupons.append(bet)

        except Exception as e:
            print(f"Błąd rozliczania meczu {bet.get('id', 'unknown')}: {e}")
            updated_coupons.append(bet)

    # Zapisujemy wyniki tylko jeśli coś zostało rozliczone
    if new_history_entries:
        history.extend(new_history_entries)
        save_json(HISTORY_FILE, history)
        
        bankroll_data["bankroll"] = round(current_bankroll, 2)
        save_json(BANKROLL_FILE, bankroll_data)
        print(f"Rozliczono {len(new_history_entries)} nowych meczów.")
        
    save_json(COUPONS_FILE, updated_coupons)
    print(f"Aktualny bankroll: {bankroll_data['bankroll']} PLN")

if __name__ == "__main__":
    settle_matches()
