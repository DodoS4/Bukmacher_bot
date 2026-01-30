import os
import json
import requests
from datetime import datetime, timezone

# --- KONFIGURACJA ---
COUPONS_FILE = "coupons.json"
HISTORY_FILE = "history.json"
BANKROLL_FILE = "bankroll.json"  # KLUCZOWY PLIK DLA KULI ŚNIEŻNEJ
API_KEY = os.getenv("ODDS_KEY") 

# ================= FUNKCJE BANKROLLA =================

def update_bankroll(amount):
    """Aktualizuje saldo w bankroll.json (dodaje wygraną lub odejmuje stratę)"""
    balance = 100.0
    if os.path.exists(BANKROLL_FILE):
        try:
            with open(BANKROLL_FILE, "r") as f:
                data = json.load(f)
                balance = data.get("balance", 100.0)
        except: pass
    
    new_balance = balance + amount
    
    with open(BANKROLL_FILE, "w") as f:
        json.dump({
            "balance": round(new_balance, 2),
            "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }, f, indent=4)
    print(f"💰 Bankroll zaktualizowany: {round(new_balance, 2)} PLN")

# ================= POZOSTAŁE FUNKCJE =================

def get_match_results(sport, event_id):
    url = f"https://api.the-odds-api.com/v4/sports/{sport}/scores/"
    params = {"apiKey": API_KEY, "daysFrom": 3} # Usunięto eventId z params, by pobrać całą listę
    try:
        resp = requests.get(url, params=params, timeout=15)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"❌ Błąd API: {e}")
    return None

def settle_matches():
    if not os.path.exists(COUPONS_FILE):
        print("ℹ️ Brak aktywnych kuponów.")
        return

    with open(COUPONS_FILE, "r", encoding="utf-8") as f:
        active_coupons = json.load(f)

    if not active_coupons: return

    history = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            try: history = json.load(f)
            except: history = []

    remaining_coupons = []
    new_settlements = 0
    total_session_profit = 0

    print(f"⏳ Sprawdzanie {len(active_coupons)} kuponów...")

    for coupon in active_coupons:
        results = get_match_results(coupon['sport'], coupon['id'])
        match_data = next((m for m in results if m['id'] == coupon['id']), None) if results else None

        if match_data and match_data.get('completed'):
            home_score = 0
            away_score = 0
            for score in match_data.get('scores', []):
                if score['name'] == match_data['home_team']:
                    home_score = int(score['score'])
                else:
                    away_score = int(score['score'])

            # Logika wygranej
            won = False
            if coupon['outcome'] == match_data['home_team'] and home_score > away_score:
                won = True
            elif coupon['outcome'] == match_data['away_team'] and away_score > home_score:
                won = True

            stake = float(coupon['stake'])
            odds = float(coupon['odds'])

            if won:
                # Zysk na czysto (po odjęciu stawki i podatku)
                # Wzór: (Stawka * 0.88 * Kurs) - Stawka
                profit = (stake * 0.88 * odds) - stake
                # Ale do bankrolla musimy dodać CAŁĄ wypłatę (Stake * 0.88 * Kurs) 
                # i odjąć stawkę którą już wydałeś... najprościej:
                change = (stake * 0.88 * odds) - stake 
                status = "WIN"
            else:
                profit = -stake
                change = -stake 
                # Uwaga: Jeśli bot pobiera stawkę z bankrolla w momencie wysyłania typu, 
                # tutaj nic nie odejmujemy, bo kasa już "zeszła". 
                # ALE w Twoim systemie stawka jest tylko obliczana, więc odejmujemy ją tutaj.
                status = "LOSS"

            total_session_profit += profit

            history.append({
                "id": coupon['id'], "home": coupon['home'], "away": coupon['away'],
                "sport": coupon['sport'], "outcome": coupon['outcome'], "odds": odds,
                "stake": stake, "profit": round(profit, 2), "status": status,
                "score": f"{home_score}:{away_score}", "time": coupon['time']
            })
            new_settlements += 1
            print(f"✅ {status}: {coupon['home']} - {coupon['away']} ({profit:.2f} PLN)")
        else:
            remaining_coupons.append(coupon)

    if new_settlements > 0:
        # AKTUALIZACJA KULI ŚNIEŻNEJ
        update_bankroll(total_session_profit)
        
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=4)
        with open(COUPONS_FILE, "w", encoding="utf-8") as f:
            json.dump(remaining_coupons, f, indent=4)
        print(f"🚀 Rozliczono: {new_settlements}. Profit sesji: {total_session_profit:.2f}")

if __name__ == "__main__":
    settle_matches()
