import requests, json, os
from datetime import datetime

# ================= CONFIG =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")
API_KEYS = [os.getenv(f"ODDS_KEY{i}") for i in ["", "_2", "_3", "_4", "_5"]]
API_KEYS = [k for k in API_KEYS if k]

COUPONS_FILE = "coupons.json"
MIN_ODDS = 1.2
MAX_ODDS = 15.0

TAX = 0.88  # 12% podatek

# ================= FUNKCJE =================
def send_msg(txt):
    if not T_TOKEN or not T_CHAT: return
    try:
        requests.post(f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
                      json={"chat_id": T_CHAT, "text": txt, "parse_mode": "HTML"})
    except: pass

def load_coupons():
    if not os.path.exists(COUPONS_FILE): return []
    try:
        with open(COUPONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def save_coupons(coupons):
    with open(COUPONS_FILE, "w", encoding="utf-8") as f:
        json.dump(coupons, f, indent=2, ensure_ascii=False)

def fetch_offers(league_key):
    for key in API_KEYS:
        r = requests.get(f"https://api.the-odds-api.com/v4/sports/{league_key}/odds/",
                         params={"apiKey": key, "regions": "eu", "markets": "h2h", "oddsFormat": "decimal"})
        if r.status_code == 200:
            return r.json()
    return []

def classify_bet(odd):
    if 1.2 <= odd <= 1.5:
        return "PEWNIAK"
    elif 1.5 < odd <= 15:
        return "VALUE"
    return None

# ================= SCANNER =================
def run_scanner():
    leagues = ["basketball_nba", "basketball_euroleague",
               "soccer_epl", "soccer_uefa_champs", "hockey_nhl"]  # tu możesz dodać 12-15 lig

    coupons = load_coupons()
    pewniaki = []
    value_bets = []

    for league in leagues:
        offers = fetch_offers(league)
        for game in offers:
            home = game["home_team"]
            away = game["away_team"]
            date = game.get("commence_time", datetime.utcnow().isoformat())
            for outcome in game.get("bookmakers", [{}])[0].get("markets", [{}])[0].get("outcomes", []):
                odd = outcome.get("price")
                pick = outcome.get("name")
                if not odd or odd < MIN_ODDS or odd > MAX_ODDS:
                    continue
                bet_type = classify_bet(odd)
                if not bet_type:
                    continue
                coupon = {
                    "home": home, "away": away, "pick": pick, "odds": odd,
                    "stake": 100, "status": "PENDING",
                    "league_key": league, "league": league.upper(),
                    "date": date, "type": bet_type
                }
                if bet_type == "PEWNIAK":
                    pewniaki.append(coupon)
                else:
                    value_bets.append(coupon)

    # ================= WYŚLIJ NA TELEGRAM =================
    for c in pewniaki:
        send_msg(f"🎯 PEWNIAK\n🏀 {c['home']} - {c['away']}\n📈 Kurs: {c['odds']}")
    for c in value_bets:
        send_msg(f"🎯 VALUE BET\n🏀 {c['home']} - {c['away']}\n📈 Kurs: {c['odds']}")

    coupons.extend(pewniaki + value_bets)
    save_coupons(coupons)
    print(f"[INFO] Dodano {len(pewniaki)} pewniaków i {len(value_bets)} value betów")

# ================= MAIN =================
if __name__ == "__main__":
    run_scanner()