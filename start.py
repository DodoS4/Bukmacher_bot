import os
import requests
import json

# ================= KONFIGURACJA =================
API_KEY = os.getenv("ODDS_KEY")  # Twój klucz API z The Odds API
SPORTS = ["soccer_epl", "basketball_nba", "icehockey_nhl"]  # ligi do testu
REGIONS = "uk,us,eu"  # wymagane przez API
BOOKMAKERS = "pinnacle,bet365"  # przykładowi bukmacherzy
MARKETS = "h2h"  # head-to-head, czyli typy 1X2
ODDS_FORMAT = "decimal"

# ================= FUNKCJE =================
def fetch_odds(sport):
    url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds"
    params = {
        "apiKey": API_KEY,
        "regions": REGIONS,
        "markets": MARKETS,
        "oddsFormat": ODDS_FORMAT
    }
    # Dodaj bukmacherów jeśli chcesz filtrować
    if BOOKMAKERS:
        params["bookmakers"] = BOOKMAKERS

    response = requests.get(url, params=params)
    
    if response.status_code != 200:
        print(f"❌ Błąd dla {sport}: {response.json().get('message')}")
        return []

    data = response.json()
    if not data:
        print(f"⚠️ Brak danych dla {sport}")
        return []

    return data

def display_matches(matches, sport):
    print(f"\n🔹 {sport.upper()} – {len(matches)} meczów")
    print("-" * 50)
    for match in matches:
        home = match.get("home_team")
        away = match.get("away_team")
        commence = match.get("commence_time")
        print(f"{home} vs {away} | {commence}")
        for bookmaker in match.get("bookmakers", []):
            print(f"  Bukmacher: {bookmaker['title']}")
            for market in bookmaker.get("markets", []):
                for outcome in market.get("outcomes", []):
                    print(f"    {outcome['name']}: {outcome['price']}")
        print("-" * 50)

# ================= GŁÓWNY PROGRAM =================
for sport in SPORTS:
    matches = fetch_odds(sport)
    if matches:
        display_matches(matches, sport)