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
            continue
        except: continue
    return None

def settle_matches():
    print(f"🚀 ROZPOCZĘTO ROZLICZANIE")
    api_keys = get_all_api_keys()
    if not os.path.exists(COUPONS_FILE): return
    with open(COUPONS_FILE, "r", encoding="utf-8") as f: active_coupons = json.load(f)
    if not active_coupons: return

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

    for sport in sports_to_check:
        print(f"📡 Pobieram wyniki: {sport}")
        res = get_match_results(sport, api_keys)
        if res:
            for match in res: results_map[match['id']] = match

    for coupon in active_coupons:
        match_data = results_map.get(coupon['id'])
        try:
            m_time = datetime.fromisoformat(coupon['time'].replace("Z", "+00:00"))
        except: m_time = now_utc

        if match_data and match_data.get('completed'):
            h_score, a_score = 0, 0
            for s in match_data.get('scores', []):
                if s['name'] == match_data['home_team']: h_score = int(s['score'])
                else: a_score = int(s['score'])

            won = False
            pick = coupon.get('outcome')
            if pick == match_data['home_team'] and h_score > a_score: won = True
            elif pick == match_data['away_team'] and a_score > h_score: won = True

            stake, odds = float(coupon.get('stake', 0)), float(coupon.get('odds', 0))
            profit = round((stake * odds) - stake if won else -stake, 2)

            history.append({
                "id": coupon['id'], "home": coupon['home'], "away": coupon['away'],
                "sport": coupon['sport'], "outcome": pick, "odds": odds, "stake": stake,
                "profit": profit, "status": "WIN" if won else "LOSS", "score": f"{h_score}:{a_score}"
            })
            new_settlements += 1
            print(f"{'💰' if won else '❌'} {coupon['home']} - {coupon['away']} ({h_score}:{a_score}) | {profit} PLN")
        
        elif (now_utc - m_time) > timedelta(hours=72):
            history.append({
                "id": coupon['id'], "home": coupon['home'], "away": coupon['away'],
                "sport": coupon['sport'], "profit": 0.0, "status": "VOID"
            })
            new_settlements += 1
            print(f"⚠️ VOID: {coupon['home']}")
        else:
            remaining_coupons.append(coupon)

    if new_settlements > 0:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f: json.dump(history, f, indent=4)
        with open(COUPONS_FILE, "w", encoding="utf-8") as f: json.dump(remaining_coupons, f, indent=4)

if __name__ == "__main__": settle_matches()
