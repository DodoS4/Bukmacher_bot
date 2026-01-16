import requests
import json
from datetime import datetime, timedelta, timezone

# ================= KONFIGURACJA =================
API_KEYS = [
    "ODDS_KEY_1",
    "ODDS_KEY_2",
    "ODDS_KEY_3",
    "ODDS_KEY_4",
    "ODDS_KEY_5"
]

SPORTS = {
    "basketball_nba": "🏀 NBA",
    "basketball_euroleague": "🏀 Euroleague",
    "soccer_epl": "⚽ Premier League",
    "soccer_spain_la_liga": "⚽ La Liga",
    "hockey_nhl": "🏒 NHL"
}

COUPON_FILE = "coupons.json"
MAX_HOURS_AHEAD = 48

# ================= FUNKCJE =================
def fetch_odds(api_key, sport_key):
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds"
    params = {
        "apiKey": api_key,
        "regions": "eu",
        "markets": "h2h",
        "oddsFormat": "decimal",
        "dateFormat": "iso"
    }

    print(f"[DEBUG] {sport_key} | klucz: {api_key[:6]}***")

    r = requests.get(url, params=params, timeout=15)
    if r.status_code != 200:
        print(f"[ERROR] {sport_key} | {r.status_code} | {r.text}")
        return []

    return r.json()


def is_within_48h(commence_time):
    dt = datetime.fromisoformat(commence_time.replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    return now <= dt <= now + timedelta(hours=MAX_HOURS_AHEAD)


def main():
    coupons = []
    used = set()

    for sport_key, sport_name in SPORTS.items():
        for key in API_KEYS:
            try:
                matches = fetch_odds(key, sport_key)
                if not matches:
                    continue

                for m in matches:
                    if not is_within_48h(m["commence_time"]):
                        continue

                    home = m["home_team"]
                    away = m["away_team"]
                    match_id = f"{sport_key}-{home}-{away}-{m['commence_time']}"

                    if match_id in used:
                        continue

                    bookmaker = m["bookmakers"][0]
                    outcomes = bookmaker["markets"][0]["outcomes"]

                    for o in outcomes:
                        coupons.append({
                            "league": sport_name,
                            "league_key": sport_key,
                            "home": home,
                            "away": away,
                            "pick": o["name"],
                            "odds": o["price"],
                            "status": "PENDING",
                            "date": m["commence_time"],
                            "created_at": datetime.utcnow().isoformat()
                        })

                    used.add(match_id)

                break  # sport OK → następny sport

            except Exception as e:
                print(f"[EXCEPTION] {sport_key}: {e}")

    print(f"[INFO] Dodano {len(coupons)} kuponów")

    with open(COUPON_FILE, "w", encoding="utf-8") as f:
        json.dump(coupons, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()