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
    # Sortowanie po czasie, aby wykres był poprawny
    valid_history = [m for m in history if m.get('time')]
    sorted_history = sorted(valid_history, key=lambda x: x.get('time'))
    
    for m in sorted_history:
        current_sum += float(m.get('profit', 0))
        chart_points.append(round(current_sum, 2))

    now = datetime.now(timezone.utc)
    profit_24h = 0
    for m in history:
        t_str = m.get('time')
        if not t_str: continue
        try:
            m_time = datetime.fromisoformat(t_str.replace("Z", "+00:00"))
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

def settle_matches():
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f: history = json.load(f)
        with open(COUPONS_FILE, "r", encoding="utf-8") as f: active_coupons = json.load(f)
    except Exception as e:
        print(f"Błąd wczytywania plików: {e}")
        return

    if not active_coupons: return

    still_active = []
    updated = False
    settled_count = 0
    now = datetime.now(timezone.utc)

    print(f"\n--- RAPORT ROZLICZEŃ: {now.strftime('%H:%M:%S')} ---")

    sports_to_check = list(set(c['sport'] for c in active_coupons))

    for sport in sports_to_check:
        scores_data = get_api_scores(sport)
        
        for coupon in [c for c in active_coupons if c['sport'] == sport]:
            # 1. Sprawdź, czy mecz nie jest "przestarzały" (przełożony o > 48h)
            match_date_str = coupon.get('commence_time') or coupon.get('date')
            is_expired = False
            if match_date_str:
                try:
                    # Obsługa formatu ISO z Twojego API
                    start_time = datetime.fromisoformat(match_date_str.replace("Z", "+00:00"))
                    if (now - start_time) > timedelta(hours=48):
                        is_expired = True
                except: pass

            if is_expired:
                print(f"🔄 ZWROT (48h): {coupon['home']} - {coupon['away']} | Profit: 0.00 PLN")
                history.append({
                    **coupon,
                    "status": "VOID",
                    "score": "CANCEL",
                    "profit": 0.00,
                    "time": now.isoformat()
                })
                updated = True
                settled_count += 1
                continue

            # 2. Szukaj wyniku w API
            match = next((s for s in scores_data if s['home_team'] == coupon['home'] and s['completed']), None)
            
            if match:
                try:
                    scores = match['scores']
                    h_score = int(next(s['score'] for s in scores if s['name'] == coupon['home']))
                    a_score = int(next(s['score'] for s in scores if s['name'] == coupon['away']))
                    
                    winner = coupon['home'] if h_score > a_score else (coupon['away'] if a_score > h_score else "DRAW")
                    is_win = (coupon['outcome'] == winner)
                    stake = float(coupon.get('stake', 100))
                    profit = (stake * float(coupon['odds']) - stake) if is_win else -stake

                    print(f"{'✅ ZYSK' if is_win else '❌ STRATA'}: {coupon['home']} - {coupon['away']} | {h_score}:{a_score} | {profit:+.2f} PLN")

                    history.append({
                        **coupon,
                        "status": "WIN" if is_win else "LOSS",
                        "score": f"{h_score}:{a_score}",
                        "profit": round(profit, 2),
                        "time": now.isoformat()
                    })
                    updated = True
                    settled_count += 1
                except: still_active.append(coupon)
            else:
                still_active.append(coupon)

    if updated:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f: json.dump(history, f, indent=4)
        with open(COUPONS_FILE, "w", encoding="utf-8") as f: json.dump(still_active, f, indent=4)

    # Statystyki końcowe
    total_profit = sum(float(m.get('profit', 0)) for m in history)
    bankroll = 5000 + total_profit # Start bankroll 5k
    wins = sum(1 for m in history if m.get('status') == 'WIN')
    total_matches = len([m for m in history if m.get('status') in ['WIN', 'LOSS']])
    accuracy = (wins / total_matches * 100) if total_matches > 0 else 0
    total_staked = sum(float(m.get('stake', 100)) for m in history if m.get('status') in ['WIN', 'LOSS'])
    yield_val = (total_profit / total_staked * 100) if total_staked > 0 else 0

    update_web_stats(history, bankroll, total_profit, accuracy, yield_val, len(still_active))
    
    if settled_count > 0:
        print(f"----------------------------------------------")
        print(f"ZAKOŃCZONO: Rozliczono {settled_count} pozycji.")
        print(f"BANKROLL: {bankroll:.2f} PLN")
    else:
        print("Brak nowych meczów do rozliczenia.")
    print(f"----------------------------------------------\n")

if __name__ == "__main__":
    settle_matches()
