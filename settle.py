import os
import json
import requests
from datetime import datetime, timezone

# --- KONFIGURACJA ---
COUPONS_FILE = "coupons.json"
HISTORY_FILE = "history.json"
API_KEY = os.getenv("ODDS_KEY")  # Twój klucz API

def get_match_results(sport, event_id):
    """Pobiera wyniki meczu z API."""
    url = f"https://api.the-odds-api.com/v4/sports/{sport}/scores/"
    params = {
        "apiKey": API_KEY,
        "daysFrom": 3,
        "eventId": event_id
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"❌ Błąd API przy sprawdzaniu wyniku: {e}")
    return None

def settle_matches():
    if not os.path.exists(COUPONS_FILE):
        print("ℹ️ Brak aktywnych kuponów do rozliczenia.")
        return

    with open(COUPONS_FILE, "r", encoding="utf-8") as f:
        active_coupons = json.load(f)

    if not active_coupons:
        print("ℹ️ Lista kuponów jest pusta.")
        return

    history = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)

    remaining_coupons = []
    new_settlements = 0

    print(f"⏳ Sprawdzanie {len(active_coupons)} kuponów...")

    for coupon in active_coupons:
        results = get_match_results(coupon['sport'], coupon['id'])
        match_data = next((m for m in results if m['id'] == coupon['id']), None) if results else None

        if match_data and match_data.get('completed'):
            home_score, away_score = 0, 0
            for score in match_data.get('scores', []):
                if score['name'] == match_data['home_team']:
                    home_score = int(score['score'])
                else:
                    away_score = int(score['score'])

            # Sprawdzenie wygranej
            won = False
            if coupon['outcome'] == match_data['home_team'] and home_score > away_score:
                won = True
            elif coupon['outcome'] == match_data['away_team'] and away_score > home_score:
                won = True

            # ================= OBLICZENIA BEZ PODWÓJNEGO PODATKU =================
            stake = float(coupon['stake'])       # już netto po 12% z start.py
            odds = float(coupon['odds'])

            if won:
                profit = (stake * odds) - stake
                status = "WIN"
            else:
                profit = -stake
                status = "LOSS"
            # ====================================================================

            # Dodanie do historii z polem stake_gross dla przejrzystości
            history.append({
                "id": coupon['id'],
                "home": coupon['home'],
                "away": coupon['away'],
                "sport": coupon['sport'],
                "outcome": coupon['outcome'],
                "odds": odds,
                "stake": stake,                 # netto
                "stake_gross": round(stake / 0.88, 2),  # przed podatkiem
                "profit": round(profit, 2),
                "status": status,
                "score": f"{home_score}:{away_score}",
                "time": coupon['time']
            })
            new_settlements += 1
            print(f"✅ Rozliczono: {coupon['home']} - {coupon['away']} | Status: {status} | Profit: {profit:.2f}")
        else:
            remaining_coupons.append(coupon)

    # Zapisywanie zmian
    if new_settlements > 0:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=4)
        with open(COUPONS_FILE, "w", encoding="utf-8") as f:
            json.dump(remaining_coupons, f, indent=4)
        print(f"🚀 Zakończono! Rozliczono nowych meczów: {new_settlements}")
    else:
        print("ℹ️ Brak nowych meczów do rozliczenia.")

if __name__ == "__main__":
    settle_matches()
