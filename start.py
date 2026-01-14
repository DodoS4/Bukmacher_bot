import requests, json, os
from datetime import datetime

T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT_RESULTS")
API_KEYS = [os.getenv(f"ODDS_KEY{i}") for i in ["", "_2", "_3", "_4", "_5"]]
API_KEYS = [k for k in API_KEYS if k]
COUPONS_FILE = "coupons.json"
TAX_PL = 0.88  # 12% podatek

# ===== 15 lig do monitorowania =====
LEAGUES = [
    "basketball_nba", "basketball_euroleague",
    "soccer_epl", "soccer_la_liga", "soccer_serie_a",
    "soccer_bundesliga", "soccer_ligue1", "soccer_eredivisie",
    "hockey_nhl", "hockey_khl", "basketball_wnba",
    "basketball_nbl", "soccer_primera_liga",
    "soccer_turkish_super_lig", "basketball_cba"
]

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
    except: return []

def save_coupons(coupons):
    with open(COUPONS_FILE, "w", encoding="utf-8") as f:
        json.dump(coupons, f, indent=2)

def fetch_offers(league_key):
    for key in API_KEYS:
        try:
            r = requests.get(f"https://api.the-odds-api.com/v4/sports/{league_key}/odds/",
                             params={"apiKey": key, "regions": "eu", "markets": "h2h", "oddsFormat": "decimal"})
            if r.status_code == 200:
                return r.json()
        except: continue
    return []

def generate_coupons():
    coupons = load_coupons()
    for league in LEAGUES:
        offers = fetch_offers(league)
        for o in offers:
            home = o["home_team"]
            away = o["away_team"]
            for book in o.get("bookmakers", []):
                for market in book.get("markets", []):
                    for outcome in market.get("outcomes", []):
                        pick = outcome["name"]
                        odds = outcome["price"]
                        # value + pewniaki: edge > 0.5% lub odds < 1.5
                        edge = (odds - 1) * 100
                        if edge > 0.5 or odds < 1.5:
                            coupon = {
                                "home": home,
                                "away": away,
                                "pick": pick,
                                "odds": odds,
                                "stake": 100,  # stała stawka
                                "status": "PENDING",
                                "league_key": league,
                                "league_name": league,
                                "date": o.get("commence_time"),
                                "edge": round(edge,2)
                            }
                            if coupon not in coupons:
                                coupons.append(coupon)
    save_coupons(coupons)
    send_msg(f"📌 Dodano {len(coupons)} kuponów do {COUPONS_FILE}")

if __name__ == "__main__":
    generate_coupons()