import requests
import os

API_KEYS = [k for k in [
    os.getenv("ODDS_KEY"),
    os.getenv("ODDS_KEY_2"),
    os.getenv("ODDS_KEY_3"),
    os.getenv("ODDS_KEY_4"),
    os.getenv("ODDS_KEY_5")
] if k]

def available_leagues():
    for key in API_KEYS:
        r = requests.get(f"https://api.the-odds-api.com/v4/sports", params={"apiKey": key})
        if r.status_code == 200:
            leagues = r.json()
            print("Dostępne ligi dla tego klucza:")
            for lg in leagues:
                print(lg["key"])
            break
        else:
            print(f"Błąd: {r.status_code} - {r.text[:200]}")

available_leagues()