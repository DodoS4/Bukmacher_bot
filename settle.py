import os
import json
import requests
import time
from datetime import datetime, timezone, timedelta

# --- KONFIGURACJA PLIKÓW ---
COUPONS_FILE = "coupons.json"
HISTORY_FILE = "history.json"
STATS_JSON_FILE = "stats.json"

# --- POBIERANIE KLUCZY Z GITHUB SECRETS (TWOJE NAZWY) ---
def get_api_keys():
    keys = []
    # 1. Sprawdź pierwszy klucz ODDS_KEY
    first_key = os.getenv('ODDS_KEY')
    if first_key:
        keys.append(first_key.strip())
    
    # 2. Sprawdź kolejne klucze ODDS_KEY2, ODDS_KEY3... aż do 10
    for i in range(2, 11):
        key = os.getenv(f'ODDS_KEY{i}')
        if key:
            keys.append(key.strip())
            
    return keys

API_KEYS = get_api_keys()
current_key_index = 0

def get_api_scores(sport):
    """Pobiera wyniki z The Odds API z obsługą rotacji kluczy."""
    global current_key_index
    if not API_KEYS:
        print("❌ DEBUG CRITICAL: Nie znaleziono kluczy ODDS_KEY w GitHub Secrets!")
        return []

    for _ in range(len(API_KEYS)):
        api_key = API_KEYS[current_key_index]
        print(f"🔄 DEBUG: Próba kluczem {current_key_index + 1}/{len(API_KEYS)} dla {sport}...")
        
        url = f"https://api.the-odds-api.com/v4/sports/{sport}/scores/?apiKey={api_key}&daysFrom=3"
        try:
            response = requests.get(url, timeout=15)
            if response.status_code == 200:
                return response.json()
            elif response.status_code in [401, 429]:
                print(f"⚠️ DEBUG: Klucz nr {current_key_index + 1} nieaktywny ({response.status_code}). Rotacja...")
                current_key_index = (current_key_index + 1) % len(API_KEYS)
                continue
            else:
                print(f"❌ DEBUG ERROR: Status {response.status_code}")
                return []
        except Exception as e:
            print(f"❌ DEBUG ERROR: Połączenie: {e}")
            current_key_index = (current_key_index + 1) % len(API_KEYS)
            
    return []

def update_web_stats(history, bankroll, total_profit, accuracy, yield_val, active_count):
    """Aktualizuje stats.json pod dashboard HTML."""
    print("📊 DEBUG: Odświeżanie statystyk...")
    
    chart_points = []
    current_sum = 0
    sorted_history = sorted(history, key=lambda x: x.get('time', ''))
    for m in sorted_history:
        current_sum += float(m.get('profit', 0))
        chart_points.append(round(current_sum, 2))

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
    print(f"✅ DEBUG: Dane zapisane. Profit: {total_profit}")

def settle_matches():
    print(f"\n{'='*60}")
    print(f"🕒 DEBUG START: {datetime.now().strftime('%H:%M:%S')}")
    
    try:
        if not os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "w") as f: json.dump([], f)
            
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)
        with open(COUPONS_FILE, "r", encoding="utf-8") as f:
            active_coupons = json.load(f)
    except Exception as e:
        print(f"❌ DEBUG ERROR: Błąd plików: {e}")
        return

    if not active_coupons:
        print("ℹ️ DEBUG: Brak typów do rozliczenia.")
    else:
        still_active = []
        updated = False
        sports_to_check = list(set(c['sport'] for c in active_coupons))

        for sport in sports_to_check:
            scores_data = get_api_scores(sport)
            
            for coupon in [c for c in active_coupons if c['sport'] == sport]:
                # Szukamy meczu zakończonego
                match = next((s for s in scores_data if s['home_team'] == coupon['home'] and s['completed']), None)
                
                if match:
                    try:
                        scores = match['scores']
                        h_score = int(next(s['score'] for s in scores if s['name'] == coupon['home']))
                        a_score = int(next(s['score'] for s in scores if s['name'] == coupon['away']))
                        
                        print(f"🎯 MATCH: {coupon['home']} {h_score}:{a_score} {coupon['away']}")
                        
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
                    except Exception:
                        still_active.append(coupon)
                else:
                    still_active.append(coupon)

        if updated:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(history, f, indent=4)
            with open(COUPONS_FILE, "w", encoding="utf-8") as f:
                json.dump(still_active, f, indent=4)

    # --- OBLICZENIA ---
    total_profit = sum(float(m.get('profit', 0)) for m in history)
    bankroll = 5000 + total_profit
    wins = sum(1 for m in history if m.get('status') == 'WIN')
    total_matches = len(history)
    accuracy = (wins / total_matches * 100) if total_matches > 0 else 0
    total_staked = sum(float(m.get('stake', 100)) for m in history)
    yield_val = (total_profit / total_staked * 100) if total_staked > 0 else 0

    update_web_stats(history, bankroll, total_profit, accuracy, yield_val, len(active_coupons if not updated else still_active))
    print(f"🏁 DEBUG KONIEC\n")

if __name__ == "__main__":
    settle_matches()
