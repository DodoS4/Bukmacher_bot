import json
from datetime import datetime

COUPON_FILE = "coupons.json"
RESULTS_FILE = "results.json"  # Tutaj można trzymać rozliczone kupony

# Funkcja symulująca pobranie wyniku meczu
# W produkcji możesz podpiąć API wyników (np. sportsdata.io, api-football)
def get_match_result(sport, home_team, away_team):
    # Dummy: w realnym systemie podajesz wynik z API
    # Zwraca nazwę zwycięzcy lub "Draw"
    # Tu na razie symulacja
    return None

def settle_coupons():
    try:
        with open(COUPON_FILE, "r", encoding="utf-8") as f:
            coupons = json.load(f)
    except FileNotFoundError:
        print("[WARN] Brak pliku coupons.json")
        return

    results = []
    for c in coupons:
        result = get_match_result(c["sport"], c["home_team"], c["away_team"])
        if result is None:
            status = "pending"
            profit = 0
        elif result == c["pick"]:
            status = "win"
            profit = round((c["odds"] - 1), 2)  # Stawka 1 jednostka
        else:
            status = "lose"
            profit = -1  # Stawka 1 jednostka

        results.append({
            **c,
            "status": status,
            "profit": profit
        })

    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=4)
    print(f"[INFO] Kupony rozliczone i zapisane w {RESULTS_FILE}")

if __name__ == "__main__":
    settle_coupons()