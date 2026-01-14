import os
import json
from datetime import datetime, timezone
import requests

# ================= KONFIGURACJA =================
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS")  # Telegram chat do wyników
COUPONS_FILE = "coupons.json"
SCORES_API_KEY = os.getenv("SCORES_KEY")    # API do wyników (opcjonalnie)
SCORES_API_URL = "https://api.scoresapi.io/v1/scores"  # przykład endpointu

# ================= FUNKCJE =================
def load_coupons():
    try:
        with open(COUPONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_coupons(coupons):
    with open(COUPONS_FILE, "w", encoding="utf-8") as f:
        json.dump(coupons, f, indent=2, ensure_ascii=False)

def fetch_score(league_key, home, away, date):
    """
    Pobiera wynik meczu z API scores.
    Zwraca 'home', 'away' lub None jeśli brak wyniku.
    """
    if not SCORES_API_KEY:
        return None

    try:
        params = {
            "api_key": SCORES_API_KEY,
            "league": league_key,
            "date": date[:10],  # YYYY-MM-DD
        }
        resp = requests.get(SCORES_API_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        # szukamy meczu po drużynach i czasie
        for match in data.get("matches", []):
            if match["home"] == home and match["away"] == away:
                if match.get("status") == "finished":
                    if match["home_score"] > match["away_score"]:
                        return home
                    elif match["away_score"] > match["home_score"]:
                        return away
                    else:
                        return "DRAW"
        return None
    except Exception as e:
        print(f"[WARN] Nie udało się pobrać wyniku: {e}")
        return None

def settle_coupons():
    coupons = load_coupons()
    updated = False

    for c in coupons:
        if c.get("status") == "PENDING":
            result = fetch_score(c.get("league_key"), c["home"], c["away"], c["date"])
            if result:
                if result == c["pick"]:
                    c["status"] = "WON"
                    c["profit"] = round(c["stake"] * (c["odds"] - 1), 2)
                elif result == "DRAW":
                    c["status"] = "DRAW"
                    c["profit"] = 0
                else:
                    c["status"] = "LOST"
                    c["profit"] = -c["stake"]
                c["settled_at"] = datetime.now(timezone.utc).isoformat()
                updated = True

    if updated:
        save_coupons(coupons)
        print(f"[INFO] Rozliczono kupony. Zapisano {len(coupons)} rekordów.")
    else:
        print("[INFO] Brak nowych wyników do rozliczenia.")

# ================= URUCHOMIENIE =================
if __name__ == "__main__":
    settle_coupons()