import requests
import os

# ================= CONFIG =================
API_KEYS = [k for k in [
    os.getenv("ODDS_KEY"),
    os.getenv("ODDS_KEY_2"),
    os.getenv("ODDS_KEY_3"),
    os.getenv("ODDS_KEY_4"),
    os.getenv("ODDS_KEY_5")
] if k]

# Ligi, które chcesz sprawdzić
LEAGUES = [
    "basketball_nba",
    "basketball_euroleague",
    "icehockey_nhl",
    "soccer_epl",
    "soccer_efl_champ",
    "soccer_germany_bundesliga",
    "soccer_italy_serie_a",
    "soccer_spain_la_liga",
    "soccer_france_ligue_one",
    "soccer_uefa_champs_league"
]

def test_api():
    for league in LEAGUES:
        league_ok = False
        for key in API_KEYS:
            try:
                r = requests.get(
                    f"https://api.the-odds-api.com/v4/sports/{league}/odds",
                    params={"apiKey": key, "daysFrom": 7},  # 7 dni do przodu
                    timeout=10
                )
                if r.status_code == 200:
                    data = r.json()
                    print(f"✅ {league}: {len(data)} meczów")
                    for match in data[:5]:  # pokaż 5 pierwszych meczów
                        home = match.get("home_team")
                        away = match.get("away_team")
                        print(f"   ➤ {home} vs {away}")
                    league_ok = True
                    break
                else:
                    print(f"❌ {league} - Status {r.status_code}: {r.text[:200]}")
            except Exception as e:
                print(f"❌ {league} - Error: {e}")
        if not league_ok:
            print(f"❌ {league}: niedostępna")

if __name__ == "__main__":
    test_api()