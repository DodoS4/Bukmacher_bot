import os
import json
import requests
from datetime import datetime, timezone, timedelta

COUPONS_FILE = "coupons.json"
HISTORY_FILE = "history.json"

def get_all_api_keys():
    keys = []
    for i in range(1, 11):
        key_name = "ODDS_KEY" if i == 1 else f"ODDS_KEY_{i}"
        val = os.getenv(key_name)
        if val: keys.append(val)
    return keys

def get_match_results(sport, keys):
    for key in keys:
        url = f"https://api.the-odds-api.com/v4/sports/{sport}/scores/"
        params = {"apiKey": key, "daysFrom": 3}
        try:
            resp = requests.get(url, params=params, timeout=15)
            if resp.status_code == 200: return resp.json()
            if resp.status_code == 401: continue # Klucz wygasł
        except: continue
    return None

def settle_matches():
    print(f"\n{'='*50}")
    print(f"🚀 ROZPOCZĘTO ROZLICZANIE: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
    print(f"{'='*50}")

    api_keys = get_all_api_keys()
    if not os.path.exists(COUPONS_FILE): 
        print("❌ Brak pliku coupons.json - nie ma czego rozliczać.")
        return

    with open(COUPONS_FILE, "r", encoding="utf-8") as f: 
        active_coupons = json.load(f)
    
    if not active_coupons:
        print("ℹ️ Lista aktywnych kuponów jest pusta.")
        return

    history = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f: history = json.load(f)
        except: pass

    remaining_coupons = []
    new_settlements = 0
    now_utc = datetime.now(timezone.utc)
    results_map = {}
    sports_to_check = list(set(c['sport'] for c in active_coupons))

    # --- POBIERANIE WYNIKÓW ---
    for sport in sports_to_check:
        print(f"📡 Pobieram wyniki dla ligi: {sport}...")
        res = get_match_results(sport, api_keys)
        if res:
            for match in res: results_map[match['id']] = match

    print(f"\n🧐 ANALIZA KUPONÓW ({len(active_coupons)} w grze):")
    print("-" * 50)

    for coupon in active_coupons:
        match_data = results_map.get(coupon['id'])
        try:
            # Poprawne parsowanie daty z coupons.json
            m_time = datetime.fromisoformat(coupon['time'].replace("Z", "+00:00"))
        except: 
            m_time = now_utc

        # 1. MECZ ZAKOŃCZONY I MAMY WYNIK
        if match_data and match_data.get('completed'):
            h_score, a_score = 0, 0
            for s in match_data.get('scores', []):
                if s['name'] == match_data['home_team']: h_score = int(s['score'])
                else: a_score = int(s['score'])

            won = False
            pick = coupon.get('outcome')
            
            # Logika sprawdzania wygranej
            if pick == match_data['home_team'] and h_score > a_score: won = True
            elif pick == match_data['away_team'] and a_score > h_score: won = True

            stake = float(coupon.get('stake', 0))
            odds = float(coupon.get('odds', 0))
            profit = round((stake * odds) - stake if won else -stake, 2)

            history.append({
                "id": coupon['id'], 
                "home": coupon['home'], 
                "away": coupon['away'],
                "sport": coupon['sport'], 
                "outcome": pick, 
                "odds": odds, 
                "stake": stake,
                "profit": profit, 
                "status": "WIN" if won else "LOSS", 
                "score": f"{h_score}:{a_score}",
                "date": coupon['time']
            })
            new_settlements += 1
            
            status_tag = "✅ WIN " if won else "❌ LOSS"
            print(f"{status_tag}: {coupon['home']} - {coupon['away']} | Wynik: {h_score}:{a_score} | Zysk: {profit} PLN")
        
        # 2. MECZ BARDZO STARY (POWYŻEJ 72H) A BRAK WYNIKU - ZWROT (VOID)
        elif (now_utc - m_time) > timedelta(hours=72):
            history.append({
                "id": coupon['id'], "home": coupon['home'], "away": coupon['away'],
                "sport": coupon['sport'], "profit": 0.0, "status": "VOID", "date": coupon['time']
            })
            new_settlements += 1
            print(f"⚠️ VOID: {coupon['home']} - {coupon['away']} | Brak wyników przez 72h (Zwrot stawki)")

        # 3. MECZ W TOKU LUB JESZCZE SIĘ NIE ZACZĄŁ
        else:
            remaining_coupons.append(coupon)
            status_desc = "CZEKA" if m_time > now_utc else "W TOKU"
            print(f"⏳ {status_desc}: {coupon['home']} - {coupon['away']} (Start: {m_time.strftime('%d.%m %H:%M')})")

    # --- ZAPIS I PODSUMOWANIE ---
    print("-" * 50)
    if new_settlements > 0:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f: 
            json.dump(history, f, indent=4)
        with open(COUPONS_FILE, "w", encoding="utf-8") as f: 
            json.dump(remaining_coupons, f, indent=4)
        print(f"✨ ROZLICZONO: {new_settlements} meczy. Historia została zaktualizowana.")
    else:
        print("ℹ️ Nie znaleziono żadnych nowych wyników do rozliczenia.")
    
    print(f"{'='*50}\n")

if __name__ == "__main__": 
    settle_matches()
