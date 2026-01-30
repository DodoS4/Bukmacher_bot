import os
import json
import requests
from datetime import datetime, timezone

# --- KONFIGURACJA ---
COUPONS_FILE = "coupons.json"
HISTORY_FILE = "history.json"

def get_secrets():
    """Pobiera wszystkie dostępne klucze API."""
    keys = []
    main_key = os.getenv("ODDS_KEY")
    if main_key: keys.append(main_key)
    for i in range(2, 11):
        k = os.getenv(f"ODDS_KEY_{i}")
        if k: keys.append(k)
    return keys

def get_match_results(sport, api_keys):
    """Pobiera wyniki dla dyscypliny, próbując różnych kluczy w razie błędu."""
    for key in api_keys:
        url = f"https://api.the-odds-api.com/v4/sports/{sport}/scores/"
        params = {"apiKey": key, "daysFrom": 3}
        try:
            resp = requests.get(url, params=params, timeout=15)
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code in [401, 429]:
                print(f"⚠️ Klucz {key[:5]}... nieaktywny, sprawdzam następny.")
                continue
        except: continue
    return None

def settle_matches():
    print(f"🚀 START ROZLICZANIA: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    api_keys = get_secrets()
    
    if not os.path.exists(COUPONS_FILE):
        print("ℹ️ Brak kuponów.")
        return

    with open(COUPONS_FILE, "r", encoding="utf-8") as f:
        active_coupons = json.load(f)
    if not active_coupons: return

    history = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)

    remaining_coupons = []
    new_settlements = 0
    
    # Grupowanie wyników po sporcie
    sports = list(set(c['sport'] for c in active_coupons))
    all_results = {}
    for s in sports:
        res = get_match_results(s, api_keys)
        if res:
            for match in res: all_results[match['id']] = match

    for coupon in active_coupons:
        match_data = all_results.get(coupon['id'])

        if match_data and match_data.get('completed'):
            # Wyciąganie wyników
            h_score = a_score = 0
            for s in match_data.get('scores', []):
                if s['name'] == match_data['home_team']: h_score = int(s['score'])
                else: a_score = int(s['score'])

            # Logika wygranej
            won = False
            if coupon['outcome'] == match_data['home_team'] and h_score > a_score: won = True
            elif coupon['outcome'] == match_data['away_team'] and a_score > h_score: won = True

            stake = float(coupon['stake'])
            profit = (stake * float(coupon['odds'])) - stake if won else -stake

            history.append({
                "id": coupon['id'], "home": coupon['home'], "away": coupon['away'],
                "sport": coupon['sport'], "outcome": coupon['outcome'],
                "odds": coupon['odds'], "stake": stake, "profit": round(profit, 2),
                "status": "WIN" if won else "LOSS", "score": f"{h_score}:{a_score}",
                "time": coupon['time']
            })
            new_settlements += 1
            print(f"✅ Rozliczono: {coupon['home']} - {coupon['away']} ({h_score}:{a_score})")
        else:
            remaining_coupons.append(coupon)

    if new_settlements > 0:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=4)
        with open(COUPONS_FILE, "w", encoding="utf-8") as f:
            json.dump(remaining_coupons, f, indent=4)
        print(f"🚀 Rozliczono nowych: {new_settlements}")
    else:
        print("ℹ️ Brak nowych wyników w API.")

if __name__ == "__main__":
    settle_matches()
