import os
import json
import requests
import time
from datetime import datetime, timezone, timedelta

# --- KONFIGURACJA PLIKÓW ---
COUPONS_FILE = "coupons.json"
HISTORY_FILE = "history.json"
STATS_JSON_FILE = "stats.json"
API_KEY = "TWÓJ_KLUCZ_API_ODDS_API" # <--- WKLEJ TUTAJ SWÓJ KLUCZ

def get_api_scores(sport):
    """Pobiera wyniki dla danej dyscypliny z The Odds API."""
    print(f"DEBUG: Łączenie z API dla sportu: {sport}...")
    url = f"https://api.the-odds-api.com/v4/sports/{sport}/scores/?apiKey={API_KEY}&daysFrom=3"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 429:
            print("DEBUG ERROR: Przekroczono limit zapytań API (Rate Limit)!")
            return []
        else:
            print(f"DEBUG ERROR: Błąd API {response.status_code}: {response.text}")
            return []
    except Exception as e:
        print(f"DEBUG ERROR: Wyjątek podczas połączenia z API: {e}")
        return []

def update_web_stats(history, bankroll, total_profit, accuracy, yield_val, active_count):
    """Aktualizuje plik stats.json pod Twój dashboard HTML."""
    print("DEBUG: Generowanie statystyk dla dashboardu...")
    
    # Generowanie punktów wykresu
    chart_points = []
    current_sum = 0
    sorted_history = sorted(history, key=lambda x: x.get('time', ''))
    for m in sorted_history:
        current_sum += float(m.get('profit', 0))
        chart_points.append(round(current_sum, 2))

    # Oblicz zysk 24h
    now = datetime.now(timezone.utc)
    profit_24h = 0
    for m in history:
        try:
            m_time = datetime.fromisoformat(m.get('time', '').replace("Z", "+00:00"))
            if now - m_time < timedelta(hours=24):
                profit_24h += float(m.get('profit', 0))
        except: continue

    stats_data = {
        "bankroll": round(bankroll, 2),
        "zysk_total": round(total_profit, 2),
        "zysk_24h": round(profit_24h, 2),
        "yield": round(yield_val, 2),
        "obrot": len(history),
        "upcoming_val": active_count,
        "total_bets_count": len(history),
        "last_sync": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "wykres": chart_points,
        "skutecznosc": round(accuracy, 1)
    }
    
    with open(STATS_JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(stats_data, f, indent=4)
    print("✅ DEBUG: Plik stats.json zaktualizowany pomyślnie.")

def settle_matches():
    print(f"\n{'='*60}")
    print(f"DEBUG START: {datetime.now().strftime('%H:%M:%S')}")
    
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)
        with open(COUPONS_FILE, "r", encoding="utf-8") as f:
            active_coupons = json.load(f)
        print(f"DEBUG: Wczytano {len(active_coupons)} aktywnych typów i {len(history)} historycznych.")
    except Exception as e:
        print(f"DEBUG ERROR: Krytyczny błąd wczytywania plików: {e}")
        return

    if not active_coupons:
        print("DEBUG: Brak aktywnych kuponów do sprawdzenia.")
    else:
        still_active = []
        updated = False
        sports_to_check = list(set(c['sport'] for c in active_coupons))

        for sport in sports_to_check:
            scores_data = get_api_scores(sport)
            
            for coupon in [c for c in active_coupons if c['sport'] == sport]:
                # Szukanie meczu w wynikach API
                match = next((s for s in scores_data if s['home_team'] == coupon['home'] and s['completed']), None)
                
                if match:
                    try:
                        scores = match['scores']
                        h_score = int(next(s['score'] for s in scores if s['name'] == coupon['home']))
                        a_score = int(next(s['score'] for s in scores if s['name'] == coupon['away']))
                        
                        print(f"DEBUG FOUND: {coupon['home']} {h_score}:{a_score} {coupon['away']}")
                        
                        # Logika rozliczania (HOME / AWAY / DRAW)
                        if h_score > a_score: winner = coupon['home']
                        elif a_score > h_score: winner = coupon['away']
                        else: winner = "DRAW"

                        is_win = (coupon['outcome'] == winner)
                        stake = float(coupon.get('stake', 100))
                        profit = (stake * float(coupon['odds']) - stake) if is_win else -stake

                        history.append({
                            **coupon,
                            "status": "WIN" if is_win else "LOSS",
                            "score": f"{h_score}:{a_score}",
                            "profit": round(profit, 2),
                            "time": datetime.now(timezone.utc).isoformat()
                        })
                        updated = True
                        print(f"DEBUG SETTLED: {'✅ WIN' if is_win else '❌ LOSS'} | Profit: {profit}")
                    except Exception as e:
                        print(f"DEBUG ERROR: Błąd procesowania meczu {coupon['home']}: {e}")
                        still_active.append(coupon)
                else:
                    print(f"DEBUG: Mecz {coupon['home']} nadal w grze lub brak wyniku.")
                    still_active.append(coupon)

        if updated:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(history, f, indent=4)
            with open(COUPONS_FILE, "w", encoding="utf-8") as f:
                json.dump(still_active, f, indent=4)
            print("DEBUG: Pliki JSON zaktualizowane.")

    # Obliczenia końcowe (zawsze odświeżamy statystyki)
    total_profit = sum(float(m.get('profit', 0)) for m in history)
    base_capital = 5000 # Twoja kwota bazowa
    bankroll = base_capital + total_profit
    
    wins = sum(1 for m in history if m.get('status') == 'WIN')
    total_matches = len(history)
    accuracy = (wins / total_matches * 100) if total_matches > 0 else 0
    
    total_staked = sum(float(m.get('stake', 100)) for m in history)
    yield_val = (total_profit / total_staked * 100) if total_staked > 0 else 0

    update_web_stats(history, bankroll, total_profit, accuracy, yield_val, len(active_coupons if not 'still_active' in locals() else still_active))
    
    print(f"DEBUG KONIEC: {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    settle_matches()
