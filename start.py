import requests, json, os
from datetime import datetime, timedelta, timezone

# ================= CONFIG =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")
API_KEYS = [os.getenv(f"ODDS_KEY{i}") for i in ["", "_2", "_3", "_4", "_5"]]
API_KEYS = [k for k in API_KEYS if k]
COUPONS_FILE = "coupons.json"
MAX_HOURS_AHEAD = 48  # maksymalnie 48h do przodu

# ================= HELPERS =================
def send_msg(txt):
    if not T_TOKEN or not T_CHAT: return
    try:
        requests.post(f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
                      json={"chat_id": T_CHAT, "text": txt, "parse_mode": "HTML"})
    except Exception as e:
        print(f"[ERROR] Telegram send failed: {e}")

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

# ================= FETCH ODDS =================
def fetch_odds(league_key):
    for key in API_KEYS:
        try:
            r = requests.get(f"https://api.the-odds-api.com/v4/sports/{league_key}/odds/",
                             params={"apiKey": key, "regions": "eu", "markets": "h2h", "oddsFormat": "decimal"})
            if r.status_code == 200:
                return r.json()
        except:
            continue
    return []

# ================= VALUE & SURE BET FILTER =================
def filter_bets(odds_list):
    now = datetime.now(timezone.utc)
    max_time = now + timedelta(hours=MAX_HOURS_AHEAD)
    coupons = []

    for game in odds_list:
        game_time = datetime.fromisoformat(game["commence_time"].replace("Z","+00:00"))
        if not (now <= game_time <= max_time):
            continue

        for book in game.get("bookmakers", []):
            for market in book.get("markets", []):
                if market["key"] != "h2h": continue
                for i, outcome in enumerate(market["outcomes"]):
                    pick = outcome["name"]
                    odds = outcome["price"]
                    # przykładowy prosty filtr: kurs <1.8 = pewniak, >1.8 = value
                    bet_type = "PEWNIAK" if odds < 1.8 else "VALUE"

                    coupon = {
                        "home": game["home_team"],
                        "away": game["away_team"],
                        "pick": pick,
                        "odds": odds,
                        "league": game["sport_key"].replace("_", " ").title(),
                        "league_key": game["sport_key"],
                        "status": "PENDING",
                        "bet_type": bet_type,
                        "date": game_time.isoformat()
                    }
                    coupons.append(coupon)
    return coupons

# ================= RUN =================
def run():
    all_leagues = ["basketball_nba", "basketball_euroleague",
                   "soccer_epl", "soccer_uefa_champs_league",
                   "icehockey_nhl"]  # dodaj inne ligi według potrzeb

    coupons = load_coupons()
    new_coupons = []

    for league in all_leagues:
        odds_list = fetch_odds(league)
        bets = filter_bets(odds_list)
        for bet in bets:
            # unikamy duplikatów
            if not any(c["home"] == bet["home"] and c["away"] == bet["away"] and c["pick"] == bet["pick"] for c in coupons):
                coupons.append(bet)
                new_coupons.append(bet)

    save_coupons(coupons)

    # ================= SEND TO TELEGRAM =================
    for c in new_coupons:
        txt = (f"🏀 {c['league'].title()}\n"
               f"{c['home']} 🆚 {c['away']}\n"
               f"🎯 Typ: {c['pick']} ({c['bet_type']})\n"
               f"💸 Kurs: {c['odds']} | ⏳ {c['status'].title()}\n"
               f"📅 {datetime.fromisoformat(c['date']).strftime('%d.%m.%Y %H:%M')}")
        send_msg(txt)
        print(f"[NEW COUPON] {c['home']} vs {c['away']} | {c['pick']} ({c['bet_type']})")

if __name__ == "__main__":
    run()