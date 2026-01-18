import os
import requests
import json
import time

HISTORY_FILE = "history.json"
API_KEYS = [os.getenv(k) for k in ["ODDS_KEY", "ODDS_KEY_2"] if os.getenv(k)]

def fix():
    if not os.path.exists(HISTORY_FILE): return
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        history = json.load(f)

    api_key = API_KEYS[0] if API_KEYS else None
    if not api_key: 
        print("Brak klucza API!")
        return

    updated = 0
    # Wybieramy tylko te, które nie mają wyniku
    to_fix = [m for m in history if 'score' not in m or m['score'] == '-:-']

    print(f"Znaleziono {len(to_fix)} meczów do naprawy.")

    for match in to_fix:
        # Pytamy o konkretne ID meczu - to najskuteczniejsza metoda
        m_id = match['id']
        sport = match['sport']
        url = f"https://api.the-odds-api.com/v4/sports/{sport}/scores/?apiKey={api_key}&eventIds={m_id}"
        
        try:
            resp = requests.get(url)
            if resp.status_code == 429:
                print("Limit API osiągnięty. Przerywam.")
                break
            
            results = resp.json()
            if results and isinstance(results, list) and len(results) > 0:
                api_match = results[0]
                if api_match.get('completed'):
                    scores = api_match.get('scores', [])
                    if len(scores) >= 2:
                        s1 = scores[0]['score']
                        s2 = scores[1]['score']
                        match['score'] = f"{s1}:{s2}"
                        updated += 1
                        print(f"✅ SUKCES: {match['home']} vs {match['away']} -> {match['score']}")
            
            # Mała pauza, żeby nie zablokować klucza
            time.sleep(1) 
            
        except Exception as e:
            print(f"Błąd przy ID {m_id}: {e}")

    if updated > 0:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=4)
        print(f"--- KONIEC --- Zaktualizowano {updated} pozycji.")
    else:
        print("API nie zwróciło już wyników dla tych ID. Darmowe klucze mają krótką pamięć.")

if __name__ == "__main__":
    fix()
