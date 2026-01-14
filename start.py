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

# Maksymalny czas do meczu: 48h
MAX_HOURS_AHEAD = 48

# ================= FUNKCJE =================
def get_upcoming_matches(key):
    url = f"https://api.the-odds-api.com/v4/sports/upcoming/odds/?apiKey={key}"
    try:
        print(f"[DEBUG] Pobieram mecze dla klucza {key} z URL: {url}")
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except requests.HTTPError as e:
        print(f"[ERROR] Problem z kluczem {key}: {e} | Response: {e.response.text}")
    except requests.RequestException as e:
        print(f"[ERROR] Błąd połączenia dla klucza {key}: {e}")
    return []

def filter_matches(matches):
    filtered = []
    now = datetime.utcnow()
    max_time = now + timedelta(hours=MAX_HOURS_AHEAD)
    for m in matches:
        try:
            match_time = datetime.fromisoformat(m["commence_time"].replace("Z", "+00:00"))
            if now <= match_time <= max_time:
                filtered.append({
                    "sport": m.get("sport_title"),
                    "home_team": m.get("home_team"),
                    "away_team": m.get("away_team"),
                    "commence_time": match_time.isoformat(),
                    "markets": m.get("bookmakers", [])
                })
        except Exception as e:
            print(f"[WARN] Problem z datą meczu: {m.get('home_team')} vs {m.get('away_team')} | {e}")
    return filtered

def main():
    all_matches = []
    for key in API_KEYS:
        matches = get_upcoming_matches(key)
        if matches:
            filtered = filter_matches(matches)
            print(f"[INFO] Klucz {key} pobrał {len(filtered)} ważnych meczów.")
            all_matches.extend(filtered)
        else:
            print(f"[INFO] Klucz {key} nie zwrócił meczów.")
    
    if all_matches:
        print(f"[INFO] Łącznie ważnych meczów: {len(all_matches)}")
        with open(COUPON_FILE, "w", encoding="utf-8") as f:
            json.dump(all_matches, f, ensure_ascii=False, indent=4)
        print(f"[INFO] Mecze zapisane w {COUPON_FILE}")
    else:
        print("[WARN] Brak ważnych meczów do zapisania.")

if __name__ == "__main__":
    main()