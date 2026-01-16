import json
import requests
from datetime import datetime, timezone

COUPON_FILE = "coupons.json"
RESULTS_FILE = "results.json"
SCORE_API_KEY = "TWÓJ_SCORE_API_KEY"  # np. api-football lub inny serwis wyników

# ================= FUNKCJE =================
def fetch_score(sport, home, away, date):
    """
    Pobiera wynik meczu z API. Zwraca 'home', 'away' lub 'draw'.
    """
    url = f"https://api.scoresapi.com/v1/match?sport={sport}&home={home}&away={away}&date={date}&apikey={SCORE_API_KEY}"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if not data or "score" not in data:
            return "pending"
        h, a = data["score"]["home"], data["score"]["away"]
        if h > a:
            return "home"
        elif h < a:
            return "away"
        else:
            return "draw"
    except Exception as e:
        print(f"[WARN] Problem z pobraniem wyniku {home} vs {away} | {e}")
        return "pending"

def settle_coupons():
    with open(COUPON_FILE, "r", encoding="utf-8") as f:
        coupons = json.load(f)

    results = []
    for c in coupons:
        sport = c.get("sport")
        home = c.get("home_team")
        away = c.get("away_team")
        date = c.get("commence_time")[:10]

        result = fetch_score(sport, home, away, date)
        pick = c.get("pick", c.get("home_team"))

        status = "pending"
        if result != "pending":
            if (result == "home" and pick == home) or (result == "away" and pick == away):
                status = "win"
            else:
                status = "lose"

        c["status"] = status
        results.append(c)

    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=4)

    print(f"[INFO] Rozliczono {len(results)} kuponów. Wyniki zapisane w {RESULTS_FILE}")

# ================= MAIN =================
if __name__ == "__main__":
    settle_coupons()