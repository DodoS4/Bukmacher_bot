import requests
import os

API_KEYS = [k for k in [
    os.getenv("ODDS_KEY"),
    os.getenv("ODDS_KEY_2"),
    os.getenv("ODDS_KEY_3"),
    os.getenv("ODDS_KEY_4"),
    os.getenv("ODDS_KEY_5"),
] if k]

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
    "soccer_uefa_champs_league",
]

print("🔍 TEST API – BEZ FILTRÓW\n")

working = 0
dead = 0

for league in LEAGUES:
    success = False

    for key in API_KEYS:
        try:
            r = requests.get(
                f"https://api.the-odds-api.com/v4/sports/{league}/odds",
                params={
                    "apiKey": key,
                    "regions": "eu",
                    "markets": "h2h",
                    "oddsFormat": "decimal"
                },
                timeout=10
            )

            if r.status_code != 200:
                continue

            data = r.json()

            print(f"✅ {league}: {len(data)} meczów")

            if data:
                g = data[0]
                print(f"   ➤ {g.get('home_team')} vs {g.get('away_team')}")

            success = True
            working += 1
            break

        except Exception as e:
            print(f"❌ {league}: wyjątek {e}")

    if not success:
        print(f"❌ {league}: BRAK DOSTĘPU")
        dead += 1

print("\n━━━━━━━━━━━━━━━━━━")
print(f"✅ Działa: {working} lig")
print(f"❌ Niedostępne: {dead} lig")