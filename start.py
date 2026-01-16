import requests
import json
import os
from datetime import datetime, timedelta, timezone

# ================= KONFIGURACJA =================
# Pobieranie kluczy z GitHub Secrets
API_KEYS = [os.getenv(f"ODDS_KEY_{i}") for i in range(1, 6) if os.getenv(f"ODDS_KEY_{i}")]
if not API_KEYS:
    API_KEYS = [os.getenv("ODDS_KEY")]

SPORTS = ["basketball_nba", "hockey_nhl", "soccer_epl", "soccer_spain_la_liga"]
COUPON_FILE = "coupons.json"

# POLUZOWANE FILTRY DLA TESTU
MIN_ODDS = 1.20
MAX_ODDS = 3.50
MAX_HOURS_AHEAD = 72 # Zwiększone do 3 dni

def get_matches(sport, key):
    url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
    params = {
        'apiKey': key,
        'regions': 'eu',
        'markets': 'h2h',
        'oddsFormat': 'decimal'
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        print(f"[DEBUG] API Status dla {sport}: {resp.status_code}")
        if resp.status_code == 200:
            return resp.json()
        return []
    except Exception as e:
        print(f"[ERROR] {sport}: {e}")
        return []

def main():
    all_filtered_matches = []
    now = datetime.now(timezone.utc)
    max_time = now + timedelta(hours=MAX_HOURS_AHEAD)

    for sport in SPORTS:
        print(f"\n--- Sprawdzam sport: {sport} ---")
        matches = []
        for key in API_KEYS:
            if not key: continue
            matches = get_matches(sport, key)
            if matches: break # Jeśli mamy dane, nie sprawdzamy kolejnych kluczy

        print(f"[DEBUG] Znaleziono meczów w API dla {sport}: {len(matches)}")

        for m in matches:
            try:
                m_time = datetime.fromisoformat(m["commence_time"].replace("Z", "+00:00"))
                
                # Logika filtrowania
                if not (now <= m_time <= max_time):
                    continue

                if not m.get("bookmakers"):
                    continue

                # Bierzemy pierwszego bukmachera i sprawdzamy kursy
                outcomes = m["bookmakers"][0]["markets"][0]["outcomes"]
                for outcome in outcomes:
                    odds = outcome["price"]
                    if MIN_ODDS <= odds <= MAX_ODDS:
                        all_filtered_matches.append({
                            "id": m["id"],
                            "sport_key": sport,
                            "sport": m["sport_title"],
                            "home": m["home_team"],
                            "away": m["away_team"],
                            "time": m["commence_time"],
                            "odds": odds,
                            "pick": outcome["name"]
                        })
                        print(f"[MATCH] Znaleziono: {m['home']} vs {m['away']} - Kurs: {odds}")
                        break # Jeden typ na mecz wystarczy
            except Exception as e:
                print(f"[WARN] Błąd meczu: {e}")

    # Zapisywanie (z zabezpieczeniem przed pustym {})
    if all_filtered_matches:
        with open(COUPON_FILE, "w", encoding="utf-8") as f:
            json.dump(all_filtered_matches, f, indent=4, ensure_ascii=False)
        print(f"\n[SUCCESS] Zapisano {len(all_filtered_matches)} ofert do {COUPON_FILE}")
    else:
        # Bardzo ważne: jeśli nic nie ma, zapisujemy pustą listę, nie pusty słownik
        with open(COUPON_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)
        print("\n[INFO] Brak meczów spełniających kryteria.")

if __name__ == "__main__":
    main()
