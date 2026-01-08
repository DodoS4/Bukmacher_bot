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

# Lig, które chcesz przetestować
LEAGUES = [
    "icehockey_nhl",
    "icehockey_khl",
    "basketball_nba",
    "basketball_euroleague",
    "soccer_epl",
    "soccer_england_championship",
    "soccer_poland_ekstraklasa",
    "soccer_germany_bundesliga",
    "soccer_uefa_champs_league",
    "soccer_italy_serie_a",
    "soccer_spain_la_liga",
    "soccer_italy_serie_b",
    "soccer_france_ligue_1"
]

# ================= TEST SCAN =================
def scan_offers_test():
    total_scanned = 0
    total_selected = 0
    working_leagues = []
    unavailable_leagues = []

    print("🔍 TEST API – BEZ FILTRÓW\n")

    for league in LEAGUES:
        league_has_data = False
        for key in API_KEYS:
            try:
                r = requests.get(
                    f"https://api.the-odds-api.com/v4/sports/{league}/odds",
                    params={"apiKey": key, "daysFrom": 72},  # okno 72h
                    timeout=10
                )
                if r.status_code != 200:
                    continue

                data = r.json()
                if not data:
                    continue

                league_has_data = True
                total_scanned += len(data)
                total_selected += len(data)  # traktujemy wszystkie mecze jako "value-bety" w teście

                print(f"✅ {league}: {len(data)} meczów")
                for game in data[:3]:  # pokazujemy max 3 mecze na ligę
                    home = game.get("home_team", "")
                    away = game.get("away_team", "")
                    print(f"    ➤ {home} vs {away}")

                break  # jeśli klucz działa, nie próbujemy następnego

            except Exception as e:
                continue

        if league_has_data:
            working_leagues.append(league)
        else:
            unavailable_leagues.append(league)

    print("\n━━━━━━━━━━━━━━━━━━")
    print(f"Zeskanowano: {total_scanned} meczów")
    print(f"Wybrano: {total_selected} value-betów")
    print(f"✅ Działa: {len(working_leagues)} lig")
    print(f"❌ Niedostępne: {len(unavailable_leagues)} lig")
    if unavailable_leagues:
        print("    ", unavailable_leagues)


if __name__ == "__main__":
    scan_offers_test()