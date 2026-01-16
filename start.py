import requests
import json
import os
from datetime import datetime, timedelta, timezone
import hashlib

# ================= CONFIG =================
API_KEYS = [
    os.getenv("ODDS_KEY"),
    os.getenv("ODDS_KEY_2"),
    os.getenv("ODDS_KEY_3"),
    os.getenv("ODDS_KEY_4"),
    os.getenv("ODDS_KEY_5"),
]
API_KEYS = [k for k in API_KEYS if k]

COUPON_FILE = "coupons.json"
MAX_HOURS_AHEAD = 48

SPORTS = {
    "soccer_epl": "⚽ Premier League",
    "soccer_spain_la_liga": "⚽ La Liga",
    "soccer_germany_bundesliga": "⚽ Bundesliga",
    "soccer_france_ligue_one": "⚽ Ligue 1",
    "soccer_italy_serie_a": "⚽ Serie A",
}

# ================= HELPERS =================
def load_coupons():
    if not os.path.exists(COUPON_FILE):
        return []
    with open(COUPON_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_coupons(data):
    with open(COUPON_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def coupon_id(match_id, pick):
    raw = f"{match_id}-{pick}"
    return hashlib.md5(raw.encode()).hexdigest()

# ================= API =================
def fetch_matches(api_key, sport):
    url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds"
    params = {
        "apiKey": api_key,
        "regions": "eu",
        "markets": "h2h",
        "oddsFormat": "decimal"
    }
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    return r.json()

# ================= MAIN =================
def main():
    now = datetime.now(timezone.utc)
    max_time = now + timedelta(hours=MAX_HOURS_AHEAD)

    coupons = load_coupons()
    existing_ids = {c["id"] for c in coupons}
    added = 0

    for sport, sport_name in SPORTS.items():
        for key in API_KEYS:
            try:
                print(f"[DEBUG] {sport} | klucz: {key[:6]}***")
                matches = fetch_matches(key, sport)

                for m in matches:
                    match_time = datetime.fromisoformat(
                        m["commence_time"].replace("Z", "+00:00")
                    )
                    if not (now <= match_time <= max_time):
                        continue

                    market = m["bookmakers"][0]["markets"][0]["outcomes"]

                    for o in market:
                        pick = o["name"]
                        odds = o["price"]
                        cid = coupon_id(m["id"], pick)

                        if cid in existing_ids:
                            continue

                        coupons.append({
                            "id": cid,
                            "match_id": m["id"],
                            "league": sport_name,
                            "home": m["home_team"],
                            "away": m["away_team"],
                            "pick": pick,
                            "odds": odds,
                            "date": match_time.isoformat(),
                            "status": "pending",
                            "stake": 50,
                            "profit": 0
                        })
                        existing_ids.add(cid)
                        added += 1

                break  # sport OK → nie męcz kolejnych kluczy

            except Exception as e:
                print(f"[ERROR] {sport} | {e}")

    save_coupons(coupons)
    print(f"[INFO] Dodano {added} kuponów")

if __name__ == "__main__":
    main()