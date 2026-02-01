import os
import json
import requests
from datetime import datetime, timezone, timedelta

# --- KONFIGURACJA PLIKÓW ---
COUPONS_FILE = "coupons.json"
HISTORY_FILE = "history.json"
STATS_JSON_FILE = "stats.json"

def get_api_keys():
    keys = []
    # Szukamy kluczy ODDS_KEY, ODDS_KEY2, itd.
    first = os.getenv('ODDS_KEY')
    if first: keys.append(first.strip())
    for i in range(2, 11):
        k = os.getenv(f'ODDS_KEY{i}')
        if k: keys.append(k.strip())
    return keys

API_KEYS = get_api_keys()
current_key_index = 0

def get_api_scores(sport):
    global current_key_index
    if not API_KEYS: return []
    
    # Próba naprawy slugów lig (niektóre API wymagają krótszych nazw)
    sport_clean = sport.replace("soccer_", "soccer_").replace("icehockey_", "icehockey_")
    
    for _ in range(len(API_KEYS)):
        api_key = API_KEYS[current_key_index]
        url = f"https://api.the-odds-api.com/v4/sports/{sport_clean}/scores/?apiKey={api_key}&daysFrom=1"
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                return response.json()
            elif response.status_code in [401, 429]:
                current_key_index = (current_key_index + 1) % len(API_KEYS)
                continue
            else:
                return []
        except:
            current_key_index = (current_key_index + 1) % len(API_KEYS)
    return []

def settle_matches():
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f: history = json.load(f)
        with open(COUPONS_FILE, "r", encoding="utf-8") as f: active_coupons = json.load(f)
    except: return

    if not active_coupons: return

    still_active, updated, settled_count = [], False, 0
    now = datetime.now(timezone.utc)
    sports_to_check = list(set(c['sport'] for c in active_coupons))

    print(f"\n--- RAPORT ROZLICZEŃ: {now.strftime('%H:%M:%S')} ---")

    for sport in sports_to_check:
        scores_data = get_api_scores(sport)
        
        for coupon in [c for c in active_coupons if c['sport'] == sport]:
            # Elastyczne dopasowanie meczu
            # Sprawdzamy 'completed' LUB czy istnieją już jakiekolwiek wyniki punktowe
            match = next((s for s in scores_data if 
                          (coupon['home'].lower() in s['home_team'].lower() or s['home_team'].lower() in coupon['home'].lower()) 
                          and (s.get('completed') == True or s.get('scores') is not None)), None)
            
            if match and match.get('scores'):
                try:
                    scores = match['scores']
                    h_score = int(next(s['score'] for s in scores if s['name'] == match['home_team']))
                    a_score = int(next(s['score'] for s in scores if s['name'] == match['away_team']))
                    
                    winner = match['home_team'] if h_score > a_score else (match['away_team'] if a_score > h_score else "DRAW")
                    
                    # Logika sprawdzania typu
                    outcome_normalized = coupon['outcome'].lower()
                    if outcome_normalized == "draw":
                        is_win = (winner == "DRAW")
                    else:
                        is_win = (outcome_normalized in winner.lower())

                    stake = float(coupon.get('stake', 100))
                    profit = (stake * float(coupon['odds']) - stake) if is_win else -stake

                    print(f"{'✅ ZYSK' if is_win else '❌ STRATA'}: {coupon['home']} {h_score}:{a_score} {coupon['away']} | {profit:+.2f} PLN")
                    
                    history.append({**coupon, "status": "WIN" if is_win else "LOSS", "score": f"{h_score}:{a_score}", "profit": round(profit, 2), "time": now.isoformat()})
                    updated = True
                    settled_count += 1
                except:
                    still_active.append(coupon)
            else:
                # Jeśli mecz nie został znaleziony, sprawdź czy nie minęło 48h (VOID)
                start_time_str = coupon.get('commence_time') or coupon.get('date')
                is_void = False
                if start_time_str:
                    try:
                        st = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
                        if (now - st) > timedelta(hours=48):
                            is_void = True
                    except: pass
                
                if is_void:
                    print(f"🔄 ZWROT (48h): {coupon['home']} - {coupon['away']}")
                    history.append({**coupon, "status": "VOID", "score": "CANCEL", "profit": 0.00, "time": now.isoformat()})
                    updated = True
                    settled_count += 1
                else:
                    still_active.append(coupon)

    if updated:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f: json.dump(history, f, indent=4)
        with open(COUPONS_FILE, "w", encoding="utf-8") as f: json.dump(still_active, f, indent=4)
        # Wywołaj update statystyk (zakładając że masz tę funkcję z poprzednich wersji)
        # update_web_stats(...) 

    print(f"--- KONIEC: Rozliczono {settled_count} ---")

if __name__ == "__main__":
    settle_matches()
