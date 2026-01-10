import requests
import json
import os
from datetime import datetime, timedelta, timezone
from dateutil import parser

# ================= CONFIG =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS")
API_KEYS = [os.getenv(f"ODDS_KEY_{i}") for i in range(1,6)]

MAX_HOURS_AHEAD = 24
BANKROLL_FILE = "bankroll.json"
COUPONS_FILE = "coupons.json"

# ================= HELPERS =================
def load_json(filename, default):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    return default

def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def calc_stake(bankroll, edge):
    """Stawka zależna od edge i bankrolla"""
    if edge <= 0:
        return 0
    return round(bankroll * min(edge, 0.05), 2)  # max 5% bankrolla na typ

# ================= LOAD DATA =================
bankroll_data = load_json(BANKROLL_FILE, {"bankroll": 1000})
coupons = load_json(COUPONS_FILE, [])

# ================= MAIN LOOP =================
def fetch_odds():
    events = []
    for league in ["soccer_epl", "soccer_germany_bundesliga", "soccer_italy_serie_a"]:
        for key in API_KEYS:
            try:
                r = requests.get(f"https://api.the-odds-api.com/v4/sports/{league}/odds", params={"apiKey": key, "regions": "eu", "markets": "h2h"})
                if r.status_code == 200:
                    events.extend(r.json())
                    break
                elif r.status_code == 401:
                    continue
            except Exception as e:
                print(f"[ERROR] {league} key {key}: {e}")
    return events

def calculate_consensus(odds_list):
    """Konsensus kursów"""
    if not odds_list:
        return None
    return round(sum(odds_list)/len(odds_list),2)

def process_events(events):
    new_coupons = []
    for e in events:
        start_time = parser.isoparse(e['commence_time'])
        if start_time > datetime.utcnow().replace(tzinfo=timezone.utc) + timedelta(hours=MAX_HOURS_AHEAD):
            continue  # poza limitem

        teams = e['teams']
        odds = e.get('bookmakers', [])
        team_odds = {team: [] for team in teams}
        draws = []

        for b in odds:
            for m in b.get('markets', []):
                if m['key'] == 'h2h':
                    for i, t in enumerate(teams):
                        team_odds[t].append(m['outcomes'][i]['price'])
                    if len(m['outcomes']) == 3:
                        draws.append(m['outcomes'][2]['price'])

        consensus = {t: calculate_consensus(v) for t,v in team_odds.items()}
        consensus['Draw'] = calculate_consensus(draws)

        # ================= VALUE BET CALC =================
        for outcome, odd in consensus.items():
            if odd is None:
                continue
            prob = 1/odd
            edge = prob - (1 - prob)
            stake = calc_stake(bankroll_data["bankroll"], edge)
            if stake <= 0:
                continue

            coupon = {
                "match": f"{teams[0]} vs {teams[1]}",
                "pick": outcome,
                "odds": odd,
                "stake": stake,
                "timestamp": datetime.utcnow().isoformat()
            }

            # unikamy duplikatów
            if coupon not in coupons and coupon not in new_coupons:
                new_coupons.append(coupon)

    return new_coupons

def send_to_telegram(coupons_list):
    for c in coupons_list:
        text = f"🏆 {c['match']}\n🎯 Typ: {c['pick']}\n💰 Kurs: {c['odds']}\n💵 Stawka: {c['stake']} zł"
        requests.post(f"https://api.telegram.org/bot{T_TOKEN}/sendMessage", data={"chat_id": T_CHAT, "text": text})

# ================= RUN =================
if __name__ == "__main__":
    import sys
    stats_only = "--stats" in sys.argv

    events = fetch_odds()
    new_coupons = process_events(events)

    if not stats_only:
        if new_coupons:
            send_to_telegram(new_coupons)
            coupons.extend(new_coupons)
        save_json(COUPONS_FILE, coupons)
        save_json(BANKROLL_FILE, bankroll_data)
    else:
        # wysyłanie statystyk
        text = f"📊 Bankroll: {bankroll_data['bankroll']} zł\nLiczba kuponów: {len(coupons)}"
        requests.post(f"https://api.telegram.org/bot{T_TOKEN}/sendMessage", data={"chat_id": T_CHAT_RESULTS, "text": text})