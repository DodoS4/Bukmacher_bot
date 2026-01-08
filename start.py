import requests
import os
from datetime import datetime, timedelta, timezone

# ================= CONFIG =================
API_KEYS = [k for k in [
    os.getenv("ODDS_KEY"),
    os.getenv("ODDS_KEY_2"),
    os.getenv("ODDS_KEY_3"),
    os.getenv("ODDS_KEY_4"),
    os.getenv("ODDS_KEY_5")
] if k]

MAX_HOURS_AHEAD = 72  # okno 72h

# ================= TEST SKAN =================
def test_api_keys():
    for key in API_KEYS:
        try:
            r = requests.get("https://api.the-odds-api.com/v4/sports/", params={"apiKey": key}, timeout=10)
            if r.status_code != 200:
                print(f"❌ Klucz {key[:5]}… nie działa, kod: {r.status_code}")
                continue
            data = r.json()
            leagues = [l['key'] for l in data]
            print(f"✅ Klucz {key[:5]}… działa, dostępne ligi: {leagues}")
            return key, leagues
        except Exception as e:
            print(f"❌ Błąd przy kluczu {key[:5]}…: {e}")
    return None, []

def scan_offers(key, leagues):
    total_scanned = 0
    offers = {}
    unavailable = []

    for league in leagues:
        try:
            r = requests.get(
                f"https://api.the-odds-api.com/v4/sports/{league}/odds",
                params={"apiKey": key, "daysFrom": MAX_HOURS_AHEAD},
                timeout=10
            )
            if r.status_code != 200:
                unavailable.append(league)
                continue

            data = r.json()
            offers[league] = data
            total_scanned += len(data)

        except Exception as e:
            print(f"❌ Błąd ligi {league}: {e}")
            unavailable.append(league)

    print("\n🔍 Skanowanie ofert – BEZ FILTRÓW")
    print("━━━━━━━━━━━━━━")
    for lg, games in offers.items():
        print(f"✅ {lg}: {len(games)} meczów")
        for g in games[:3]:  # pokaż max 3 przykłady
            print(f"   ➤ {g.get('home_team')} vs {g.get('away_team')}")
    print("━━━━━━━━━━━━━━")
    print(f"Zeskanowano: {total_scanned} meczów")
    print(f"✅ Działa: {len(offers)} lig")
    print(f"❌ Niedostępne: {len(unavailable)} lig -> {unavailable}")

if __name__ == "__main__":
    key, leagues = test_api_keys()
    if key and leagues:
        scan_offers(key, leagues)
    else:
        print("❌ Brak działającego klucza lub brak dostępnych lig.")