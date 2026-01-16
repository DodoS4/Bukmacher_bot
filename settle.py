import requests
import json
from datetime import datetime, timedelta
import os

COUPON_FILE = "coupons.json"
RESULTS_FILE = "results.json"
API_SCORE_KEY = os.getenv("SCORE_API_KEY")  # Twój klucz do API wyników

def load_coupons():
    try:
        with open(COUPON_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_results(results):
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=4)

def get_match_score(league, home_team, away_team, commence_time):
    # POBIERZ WYNIKI Z API
    # To przykład, trzeba dostosować do faktycznego API
    url = f"https://api.scoresapi.com/match?league={league}&home={home_team}&away={away_team}&apikey={API_SCORE_KEY}"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data.get("home_score"), data.get("away_score")
    except Exception as e:
        print(f"[WARN] Nie udało się pobrać wyniku {home_team} vs {away_team} | {e}")
        return None, None

def settle_coupons():
    coupons = load_coupons()
    results = []
    for c in coupons:
        home, away = c["home_team"], c["away_team"]
        league = c["sport_key"]
        commence_time = c["commence_time"]
        home_score, away_score = get_match_score(league, home, away, commence_time)
        if home_score is None or away_score is None:
            continue

        outcome_settled = []
        for o in c["odds"]:
            if home_score > away_score and o["name"] == home:
                result = "win"
            elif away_score > home_score and o["name"] == away:
                result = "win"
            elif home_score == away_score and o["name"].lower() == "draw":
                result = "win"
            else:
                result = "lose"
            outcome_settled.append({
                "name": o["name"],
                "price": o["price"],
                "result": result
            })
        results.append({
            "home_team": home,
            "away_team": away,
            "league": league,
            "commence_time": commence_time,
            "settled_odds": outcome_settled
        })
    save_results(results)
    print(f"[INFO] Rozliczono {len(results)} kuponów")

if __name__ == "__main__":
    settle_coupons()