import os
import json
import requests
from datetime import datetime, timezone, timedelta

# --- KONFIGURACJA PLIKÓW ---
COUPONS_FILE = "coupons.json"
HISTORY_FILE = "history.json"

def get_all_api_keys():
    """Pobiera wszystkie klucze z GitHub Secrets (ODDS_KEY, ODDS_KEY_2...10)."""
    keys = []
    k1 = os.getenv("ODDS_KEY")
    if k1: keys.append(k1)
    for i in range(2, 11):
        ki = os.getenv(f"ODDS_KEY_{i}")
        if ki: keys.append(ki)
    return keys

def get_match_results(sport, keys):
    """Pobiera wyniki meczów, rotując kluczami w razie błędów 401/429."""
    for key in keys:
        url = f"https://api.the-odds-api.com/v4/sports/{sport}/scores/"
        params = {"apiKey": key, "daysFrom": 3}
        try:
            resp = requests.get(url, params=params, timeout=15)
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code in [401, 429]:
                print(f"⚠️ Klucz {key[:5]}... zablokowany/błędny. Próba kolejnego...")
                continue
        except:
            continue
    return None

def settle_matches():
    print(f"🚀 ROZPOCZĘTO ROZLICZANIE: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    api_keys = get_all_api_keys()
    if not api_keys:
        print("❌ Błąd: Brak kluczy API w środowisku!")
        return

    if not os.path.exists(COUPONS_FILE):
        print("ℹ️ Brak aktywnych kuponów do sprawdzenia.")
        return

    with open(COUPONS_FILE, "r", encoding="utf-8") as f:
        active_coupons = json.load(f)

    if not active_coupons:
        print("ℹ️ Lista kuponów jest pusta.")
        return

    history = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
        except: pass

    remaining_coupons = []
    new_settlements = 0
    now_utc = datetime.now(timezone.utc)

    # Grupowanie sportów, aby oszczędzać zapytania API
    sports_to_check = list(set(c['sport'] for c in active_coupons))
    results_map = {}

    for sport in sports_to_check:
        res = get_match_results(sport, api_keys)
        if res:
            for match in res:
                results_map[match['id']] = match

    for coupon in active_coupons:
        match_id = coupon['id']
        match_data = results_map.get(match_id)
        
        # Parsowanie czasu meczu
        try:
            match_time = datetime.fromisoformat(coupon['time'].replace("Z", "+00:00"))
        except:
            match_time = now_utc

        # 1. ROZLICZANIE ZAKOŃCZONYCH MECZÓW
        if match_data and match_data.get('completed'):
            home_score = 0
            away_score = 0
            for score in match_data.get('scores', []):
                if score['name'] == match_data['home_team']:
                    home_score = int(score['score'])
                else:
                    away_score = int(score['score'])

            won = False
            if coupon['outcome'] == match_data['home_team'] and home_score > away_score:
                won = True
            elif coupon['outcome'] == match_data['away_team'] and away_score > home_score:
                won = True

            stake = float(coupon['stake'])
            odds = float(coupon['odds'])
            profit = (stake * odds) - stake if won else -stake

            history.append({
                "id": coupon['id'],
                "home": coupon['home'],
                "away": coupon['away'],
                "sport": coupon['sport'],
                "outcome": coupon['outcome'],
                "odds": odds,
                "stake": stake,
                "profit": round(profit, 2),
                "status": "WIN" if won else "LOSS",
                "score": f"{home_score}:{away_score}",
                "time": coupon['time']
            })
            new_settlements += 1
            print(f"✅ {status_icon(won)} {coupon['home']} - {coupon['away']} | {home_score}:{away_score} | Profit: {profit:.2f}")

        # 2. OBSŁUGA MECZÓW PRZEŁOŻONYCH / BRAKU DANYCH (VOID po 72h)
        elif (now_utc - match_time) > timedelta(hours=72):
            history.append({
                "id": coupon['id'],
                "home": coupon['home'],
                "away": coupon['away'],
                "sport": coupon['sport'],
                "outcome": coupon['outcome'],
                "odds": float(coupon['odds']),
                "stake": float(coupon['stake']),
                "profit": 0.0,
                "status": "VOID",
                "score": "PPD",
                "time": coupon['time']
            })
            new_settlements += 1
            print(f"⚠️ VOID: {coupon['home']} - {coupon['away']} (Mecz nie odbył się w terminie)")

        # 3. MECZ NADAL OCZEKUJE
        else:
            remaining_coupons.append(coupon)

    # Zapisywanie zmian
    if new_settlements > 0:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=4)
        with open(COUPONS_FILE, "w", encoding="utf-8") as f:
            json.dump(remaining_coupons, f, indent=4)
        print(f"✨ Rozliczono nowych pozycji: {new_settlements}")
    else:
        print("ℹ️ Brak nowych meczów do rozliczenia w tej turze.")

def status_icon(won):
    return "💰 WIN" if won else "❌ LOSS"

if __name__ == "__main__":
    settle_matches()
