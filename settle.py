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
    first_key = os.getenv('ODDS_KEY')
    if first_key: keys.append(first_key.strip())
    for i in range(2, 11):
        key = os.getenv(f'ODDS_KEY{i}')
        if key: keys.append(key.strip())
    return keys

API_KEYS = get_api_keys()
current_key_index = 0

def get_api_scores(sport):
    global current_key_index
    if not API_KEYS: return []
    for _ in range(len(API_KEYS)):
        api_key = API_KEYS[current_key_index]
        url = f"https://api.the-odds-api.com/v4/sports/{sport}/scores/?apiKey={api_key}&daysFrom=3"
        try:
            response = requests.get(url, timeout=15)
            if response.status_code == 200: return response.json()
            elif response.status_code in [401, 429]:
                current_key_index = (current_key_index + 1) % len(API_KEYS)
                continue
            else: return []
        except:
            current_key_index = (current_key_index + 1) % len(API_KEYS)
    return []

def update_web_stats(history, bankroll, total_profit, accuracy, yield_val, active_count):
    chart_points = []
    current_sum = 0
    valid_history = [m for m in history if m.get('time')]
    sorted_history = sorted(valid_history, key=lambda x: x.get('time'))
    for m in sorted_history:
        current_sum += float(m.get('profit', 0))
        chart_points.append(round(current_sum, 2))

    now = datetime.now(timezone.utc)
    profit_24h = sum(float(m.get('profit', 0)) for m in history if m.get('time') and (now - datetime.fromisoformat(m.get('time').replace("Z", "+00:00"))) < timedelta(hours=24))

    stats_data = {
        "bankroll": round(bankroll, 2), "zysk_total": round(total_profit, 2),
        "zysk_24h": round(profit_24h, 2), "yield": round(yield_val, 2),
        "obrot": len(history), "upcoming_val": active_count,
        "total_bets_count": len(history), "last_sync": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "wykres": chart_points, "skutecznosc": round(accuracy, 1)
    }
    with open(STATS_JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(stats_data, f, indent=4)

def settle_matches():
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f: history = json.load(f)
        with open(COUPONS_FILE, "r", encoding="utf-8") as f: active_coupons = json.load(f)
    except: return

    if not active_coupons: return

    still_active, updated, settled_count = [], False, 0
    now = datetime.now(timezone.utc)
    print(f"\n--- RAPORT ROZLICZEŃ: {now.strftime('%H:%M:%S')} ---")

    sports_to_check = list(set(c['sport'] for c in active_coupons))

    for sport in sports_to_check:
        scores_data = get_api_scores(sport)
        
        # DEBUG: Jeśli nic nie znajduje, pokaż co widzi API
        if not any(s['completed'] for s in scores_data):
            print(f"ℹ️ DEBUG [{sport}]: API nie widzi jeszcze żadnych ZAKOŃCZONYCH meczów.")

        for coupon in [c for c in active_coupons if c['sport'] == sport]:
            # Elastyczne dopasowanie nazw (Fuzzy Match)
            match = next((s for s in scores_data if 
                          (coupon['home'].lower() in s['home_team'].lower() or s['home_team'].lower() in coupon['home'].lower()) 
                          and s['completed']), None)
            
            # Obsługa VOID (48h)
            start_time_str = coupon.get('commence_time') or coupon.get('date')
            if start_time_str:
                try:
                    st = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
                    if (now - st) > timedelta(hours=48) and not match:
                        print(f"🔄 ZWROT: {coupon['home']} (Przełożony > 48h)")
                        history.append({**coupon, "status": "VOID", "score": "CANCEL", "profit": 0.00, "time": now.isoformat()})
                        updated = True; settled_count += 1; continue
                except: pass

            if match:
                try:
                    scores = match['scores']
                    h_score = int(next(s['score'] for s in scores if s['name'] == match['home_team']))
                    a_score = int(next(s['score'] for s in scores if s['name'] == match['away_team']))
                    
                    # Logika wygranej (dopasowana do nazw z API)
                    api_winner = match['home_team'] if h_score > a_score else (match['away_team'] if a_score > h_score else "DRAW")
                    
                    # Sprawdzamy czy nasz typ pasuje do zwycięzcy z API (fuzzy check)
                    is_win = (coupon['outcome'].lower() in api_winner.lower()) if coupon['outcome'] != "DRAW" else (api_winner == "DRAW")
                    
                    stake = float(coupon.get('stake', 100))
                    profit = (stake * float(coupon['odds']) - stake) if is_win else -stake

                    print(f"{'✅ ZYSK' if is_win else '❌ STRATA'}: {coupon['home']} - {coupon['away']} ({h_score}:{a_score}) | {profit:+.2f} PLN")
                    history.append({**coupon, "status": "WIN" if is_win else "LOSS", "score": f"{h_score}:{a_score}", "profit": round(profit, 2), "time": now.isoformat()})
                    updated = True; settled_count += 1
                except Exception as e:
                    print(f"⚠️ Błąd danych dla {coupon['home']}: {e}")
                    still_active.append(coupon)
            else:
                still_active.append(coupon)

    if updated:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f: json.dump(history, f, indent=4)
        with open(COUPONS_FILE, "w", encoding="utf-8") as f: json.dump(still_active, f, indent=4)

    total_profit = sum(float(m.get('profit', 0)) for m in history)
    wins = sum(1 for m in history if m.get('status') == 'WIN')
    total_matches = len([m for m in history if m.get('status') in ['WIN', 'LOSS']])
    accuracy = (wins / total_matches * 100) if total_matches > 0 else 0
    total_staked = sum(float(m.get('stake', 100)) for m in history if m.get('status') in ['WIN', 'LOSS'])
    yield_val = (total_profit / total_staked * 100) if total_staked > 0 else 0

    update_web_stats(history, 5000 + total_profit, total_profit, accuracy, yield_val, len(still_active))
    print(f"--- KONIEC RAPORTU (Rozliczono: {settled_count}) ---\n")

if __name__ == "__main__":
    settle_matches()
