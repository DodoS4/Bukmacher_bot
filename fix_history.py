import os
import requests
import json

HISTORY_FILE = "history.json"
API_KEYS = [os.getenv(k) for k in ["ODDS_KEY", "ODDS_KEY_2"] if os.getenv(k)]

def fix():
    if not os.path.exists(HISTORY_FILE): return
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        history = json.load(f)

    api_key = API_KEYS[0] if API_KEYS else None
    if not api_key: return

    updated = 0
    # Pobieramy unikalne ligi z historii
    leagues = list(set([m['sport'] for m in history if 'score' not in m or m['score'] == '-:-']))

    for league in leagues:
        print(f"Sprawdzam: {league}")
        url = f"https://api.the-odds-api.com/v4/sports/{league}/scores/?apiKey={api_key}&daysFrom=3"
        try:
            resp = requests.get(url)
            if resp.status_code != 200: continue
            results = resp.json()

            for match in history:
                if match.get('sport') == league and ('score' not in match or match['score'] == '-:-'):
                    # Szukaj po ID
                    api_match = next((r for r in results if r['id'] == match['id']), None)
                    
                    if api_match and api_match.get('completed'):
                        scores = api_match.get('scores', [])
                        if len(scores) >= 2:
                            # Pobieramy punkty niezależnie od nazwy (kolejność Home/Away)
                            s1 = scores[0]['score']
                            s2 = scores[1]['score']
                            match['score'] = f"{s1}:{s2}"
                            updated += 1
                            print(f"✅ OK: {match['home']} vs {match['away']} -> {match['score']}")
        except: continue

    if updated > 0:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=4)
        print(f"Zaktualizowano {updated} meczów.")
    else:
        print("Nie znaleziono nowych wyników w API.")

if __name__ == "__main__":
    fix()
