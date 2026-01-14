import requests, json, os
from datetime import datetime, timezone

# ================= CONFIG =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")
API_KEYS = [os.getenv(f"ODDS_KEY{i}") for i in ["", "_2", "_3", "_4", "_5"]]
API_KEYS = [k for k in API_KEYS if k]
COUPONS_FILE = "coupons.json"
TAX_PL = 0.88  # podatek 12%

# ================= HELPERS =================
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
        json.dump(coupons, f, indent=2, ensure_ascii=False)

def fetch_offers(league_key):
    for key in API_KEYS:
        r = requests.get(f"https://api.the-odds-api.com/v4/sports/{league_key}/odds/",
                         params={"apiKey": key, "regions":"eu","markets":"h2h","oddsFormat":"decimal"})
        if r.status_code == 200: return r.json()
    return []

# ================= SCANNER =================
def generate_offers():
    leagues = ["basketball_nba","basketball_euroleague","soccer_epl","soccer_uefa_champs_league",
               "hockey_nhl","basketball_gbl","soccer_serie_a","soccer_la_liga","soccer_bundesliga",
               "basketball_wnba","soccer_ligue_one","basketball_nbl","soccer_eredivisie","basketball_ik"]
    coupons = load_coupons()
    new_coupons = []

    for league in leagues:
        offers = fetch_offers(league)
        for o in offers[:5]:  # pobierz max 5 ofert na ligę
            home, away = o["home_team"], o["away_team"]
            odds_home, odds_away = o["bookmakers"][0]["markets"][0]["outcomes"][0]["price"], o["bookmakers"][0]["markets"][0]["outcomes"][1]["price"]
            # przykładowa prosta logika: PEWNIAK <1.5, VALUE >1.8
            if odds_home < 1.5: type_bet="PEWNIAK"
            else: type_bet="VALUE BET"

            coupon = {
                "home": home,
                "away": away,
                "pick": home,
                "odds": round(odds_home,2),
                "stake": 100,
                "status": "PENDING",
                "league_key": league,
                "league": league,
                "type": type_bet,
                "date": datetime.now(timezone.utc).isoformat()
            }
            new_coupons.append(coupon)

    coupons.extend(new_coupons)
    save_coupons(coupons)

    # wysyłanie telegram
    for c in new_coupons:
        txt = (f"🎯 <b>{c['type']}</b>\n"
               f"🏀 {c['home']} - {c['away']}\n"
               f"📈 Kurs: {c['odds']}\n"
               f"💎 Edge: {round(c.get('edge',0),2)}%\n"
               f"💰 Stake: {c['stake']} zł")
        send_msg(txt)
    print(f"[INFO] Dodano {len(new_coupons)} nowych kuponów")
    
if __name__ == "__main__":
    generate_offers()