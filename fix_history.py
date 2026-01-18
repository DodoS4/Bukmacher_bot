import os
import requests
import json

# ================= KONFIGURACJA =================
HISTORY_FILE = "history.json"
API_KEYS = [os.getenv(k) for k in ["ODDS_KEY", "ODDS_KEY_2", "ODDS_KEY_3"] if os.getenv(k)]

def fix_history():
    if not os.path.exists(HISTORY_FILE):
        return

    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        history = json.load(f)

    if not API_KEYS: return
    api_key = API_KEYS[0]
    updated_count = 0
    
    matches_to_fix = [m for m in history if 'score' not in m or m['score'] == '-:-']

    for match in matches_to_fix:
        sport = match.get('sport')
        url = f"https://api.the-odds-api.com/v4/sports/{sport}/scores/"
        params = {"apiKey": api_key, "daysFrom": 3} 
        
        try:
            resp = requests.get(url, params=params)
            if resp.status_code != 200: continue
            
            results = resp.json()
            res = next((r for r in results if r['id'] == match['id']), None)
            
            if res and res.get('completed') and len(res.get('scores', [])) >= 2:
                # METODA INTELIGENTNA: 
                # Pobieramy punkty po prostu z kolejności (Home/Away w API wyników)
                s1 = res['scores'][0]['score']
                s2 = res['scores'][1]['score']
                
                # Zapisujemy wynik (zakładamy kolejność z API)
                match['score'] = f"{s1}:{s2}"
                updated_count += 1
                print(f"✅ Naprawiono mecz {match['home']} vs {match['away']} -> {match['score']}")

        except Exception as e:
            print(f"Błąd dla {match['id']}: {e}")

    if updated_count > 0:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=4)
        print(f"GOTOWE! Zaktualizowano {updated_count} pozycji.")
    else:
        print("Nie znaleziono pasujących meczów. Sprawdź czy ID meczów w history.json są poprawne.")

if __name__ == "__main__":
    fix_history()
