import requests
import json
from datetime import datetime, timedelta

# ================= KONFIGURACJA =================
API_KEYS = [
    "TWÓJ_KLUCZ_1",
    "TWÓJ_KLUCZ_2",
    "TWÓJ_KLUCZ_3",
    "TWÓJ_KLUCZ_4",
    "TWÓJ_KLUCZ_5"
]

COUPON_FILE = "coupons.json"
MAX_HOURS_AHEAD = 48

# Minimalny i maksymalny kurs
MIN_ODDS = 1.55
MAX_ODDS = 2.05
MAX_ODDS_NBA_NHL = 2.20

# Ligi i regiony
SPORTS = {
    "NBA": ("basketball_nba", "us"),
    "NHL": ("icehockey_nhl", "us"),
    "EPL": ("soccer_epl", "eu"),
    "La Liga": ("soccer_spain_la_liga", "eu"),
    "Euroleague": ("basketball_euroleague", "eu"),
    "Serie A": ("soccer_italy_serie_a", "eu"),
    "Bundesliga": ("soccer_germany_bundesliga", "eu")
}

# ================= FUNKCJE =================
def get_upcoming_matches(sport_key, region, key):
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/?apiKey={key}&regions={region}&markets=h2h"
    try:
        print(f"[DEBUG] Pobieram {sport_key} dla klucza {key}")
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except requests.HTTPError as e:
        print(f"[ERROR] {sport_key} | {e} | Response: {e.response.text}")
    except requests.RequestException as e:
        print(f"[ERROR] Błąd połączenia {sport_key}: {e}")
    return []

def filter_matches(matches, sport_name):
    filtered = []
    now = datetime.utcnow()
    max_time = now + timedelta(hours=MAX_HOURS_AHEAD)

    for m in matches:
        try:
            match_time = datetime.fromisoformat(m["commence_time"].replace("Z", "+00:00"))
            if not (now <= match_time <= max_time):
                continue

            # Sprawdź kursy H2H pierwszego bukmachera
            if not m.get("bookmakers"):
                continue
            outcomes = m["bookmakers"][0]["markets"][0]["outcomes"]
            for o in outcomes:
                odds = o["price"]
                max_limit = MAX_ODDS_NBA_NHL if sport_name in ["NBA", "NHL"] else MAX_ODDS
                if MIN_ODDS <= odds <= max_limit:
                    filtered.append({
                        "sport": sport_name,
                        "home_team": m.get("home_team"),
                        "away_team": m.get("away_team"),
                        "pick": o["name"],
                        "odds": odds,
                        "commence_time": match_time.isoformat()
                    })
        except Exception as e:
            print(f"[WARN] Problem z datą meczu: {m.get('home_team')} vs {m.get('away_team')} | {e}")
    return filtered

def remove_duplicates(coupons):
    seen = set()
    unique = []
    for c in coupons:
        key = (c["sport"], c["home_team"], c["away_team"], c["pick"])
        if key not in seen:
            unique.append(c)
            seen.add(key)
    return unique

def main():
    all_matches = []
    for sport_name, (sport_key, region) in SPORTS.items():
        for key in API_KEYS:
            matches = get_upcoming_matches(sport_key, region, key)
            if matches:
                filtered = filter_matches(matches, sport_name)
                print(f"[INFO] {sport_name} | Klucz {key} pobrał {len(filtered)} ważnych meczów.")
                all_matches.extend(filtered)
            else:
                print(f"[INFO] {sport_name} | Klucz {key} nie zwrócił meczów.")

    # Usuń duplikaty
    all_matches = remove_duplicates(all_matches)

    if all_matches:
        print(f"[INFO] Łącznie ważnych meczów: {len(all_matches)}")
        with open(COUPON_FILE, "w", encoding="utf-8") as f:
            json.dump(all_matches, f, ensure_ascii=False, indent=4)
        print(f"[INFO] Mecze zapisane w {COUPON_FILE}")
    else:
        print("[WARN] Brak ważnych meczów do zapisania.")

if __name__ == "__main__":
    main()