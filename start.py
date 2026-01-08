import os
import requests

# Pobranie kluczy z GitHub Secrets
API_KEYS = [k for k in [
    os.getenv("ODDS_KEY_1"),
    os.getenv("ODDS_KEY_2"),
    os.getenv("ODDS_KEY_3"),
    os.getenv("ODDS_KEY_4"),
    os.getenv("ODDS_KEY_5")
] if k]

LEAGUES = [
    "basketball_nba",
    "icehockey_nhl",
    "soccer_epl",
    "soccer_uefa_champs_league",
    "soccer_italy_serie_a",
    "soccer_spain_la_liga",
    "soccer_france_ligue_1"
]

print("🔎 Testowanie kluczy API i dostępności lig...")

for key in API_KEYS:
    print(f"\nKlucz: {key[:5]}***")  # nie pokazujemy całego klucza
    for league in LEAGUES:
        try:
            r = requests.get(
                f"https://api.the-odds-api.com/v4/sports/{league}/odds",
                params={"apiKey": key, "daysFrom": 3},
                timeout=10
            )
            if r.status_code == 200:
                print(f"✅ Liga {league} dostępna, pobrano {len(r.json())} meczów")
            else:
                print(f"❌ Liga {league} niedostępna, kod {r.status_code}")
        except Exception as e:
            print(f"⚠ Wyjątek dla ligi {league}: {e}")