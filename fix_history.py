import os
import requests
import json

# ================= KONFIGURACJA =================
HISTORY_FILE = "history.json"
# Próba pobrania różnych kluczy z env
API_KEYS = [os.getenv(k) for k in ["ODDS_KEY", "ODDS_KEY_2", "ODDS_KEY_3"] if os.getenv(k)]

def fix_history():
    if not os.path.exists(HISTORY_FILE):
        print("Nie znaleziono pliku history.json")
        return

    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        history = json.load(f)

    if not API_KEYS:
        print("Brak kluczy API w zmiennych środowiskowych!")
        return

    api_key = API_KEYS[0]
    updated_count = 0
    
    # Szukamy unikalnych lig, które wymagają naprawy (brak 'score' lub wynik to '-:-')
    leagues_to_check = list(set([m['sport'] for m in history if 'score' not in m or m['score'] == '-:-']))

    if not leagues_to_check:
        print("Wszystkie mecze w historii mają już przypisane wyniki.")
        return

    for league in leagues_to_check:
        print(f"Sprawdzam wyniki dla ligi: {league}...")
        url = f"https://api.the-odds-api.com/v4/sports/{league}/scores/"
        params = {"apiKey": api_key, "daysFrom": 3} 
        
        try:
            resp = requests.get(url, params=params)
            if resp.status_code != 200: 
                print(f"Błąd API ({resp.status_code}) dla ligi {league}")
                continue
            
            results = resp.json()

            for match in history:
                # Szukamy meczu bez wyniku w danej lidze
                if (match.get('sport') == league) and ('score' not in match or match['score'] == '-:-'):
                    res = next((r for r in results if r['id'] == match['id']), None)
                    if res and res.get('completed'):
                        # Wyciąganie punktów
                        h_score = next((s['score'] for s in res['scores'] if s['name'] == match['home']), None)
                        a_score = next((s['score'] for s in res['scores'] if s['name'] == match['away']), None)
                        
                        if h_score is not None and a_score is not None:
                            match['score'] = f"{h_score}:{a_score}"
                            updated_count += 1
                            print(f"Naprawiono: {match['home']} vs {match['away']} -> {match['score']}")

        except Exception as e:
            print(f"Błąd podczas przetwarzania ligi {league}: {e}")

    if updated_count > 0:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=4)
        print(f"--- SUKCES! Naprawiono {updated_count} wyników. ---")
    else:
        print("Nie znaleziono pasujących wyników w API dla brakujących meczów.")

if __name__ == "__main__":
    fix_history()
