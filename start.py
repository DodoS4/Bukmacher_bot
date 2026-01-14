import requests
import json
import os
from datetime import datetime, timezone

# ================= KONFIGURACJA =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")
API_KEYS = [os.getenv(f"ODDS_KEY{i}") for i in ["", "_2", "_3", "_4", "_5"]]
API_KEYS = [k for k in API_KEYS if k]

COUPONS_FILE = "coupons.json"

# Zakresy kursów dla pewniaków i value bet
PEWNY_MIN, PEWNY_MAX = 1.1, 1.5
VALUE_MIN, VALUE_MAX = 1.5, 3.0

# ================= TELEGRAM =================
def send_msg(txt):
    if not T_TOKEN or not T_CHAT:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
            json={"chat_id": T_CHAT, "text": txt, "parse_mode": "HTML"}
        )
    except Exception as e:
        print(f"[ERROR] Telegram: {e}")

# ================= LOAD/ SAVE COUPONS =================
def load_coupons():
    if not os.path.exists(COUPONS_FILE):
        return []
    try:
        with open(COUPONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def save_coupons(coupons):
    with open(COUPONS_FILE, "w", encoding="utf-8") as f:
        json.dump(coupons, f, indent=2, ensure_ascii=False)

# ================= FETCH OFFERS =================
def fetch_offers(league_key):
    for key in API_KEYS:
        try:
            r = requests.get(
                f"https://api.the-odds-api.com/v4/sports/{league_key}/odds/",
                params={"apiKey": key, "regions": "eu", "markets": "h2h", "oddsFormat": "decimal", "dateFormat": "iso"}
            )
            if r.status_code == 200:
                return r.json()
        except:
            continue
    return []

# ================= FILTER & SELECT BETS =================
def select_bets(offers):
    bets = []
    for game in offers:
        home, away = game["home_team"], game["away_team"]
        odds = game.get("bookmakers", [])
        if not odds: 
            continue
        # używamy pierwszego bukmachera
        markets = odds[0].get("markets", [])
        if not markets:
            continue
        h2h = markets[0].get("outcomes", [])
        if len(h2h) != 2:
            continue

        # Tworzymy typy
        for o in h2h:
            pick = o["name"]
            odd = o["price"]
            # edge dla prostego filtrowania
            edge = round((odd - 1) * 100, 2)
            # pewniaki
            if PEWNY_MIN <= odd <= PEWNY_MAX:
                bets.append({
                    "home": home,
                    "away": away,
                    "pick": pick,
                    "odds": odd,
                    "stake": 100,
                    "status": "PENDING",
                    "league_key": game["sport_key"],
                    "league_name": game["sport_title"],
                    "date": game["commence_time"],
                    "type": "PEWNY",
                    "edge": edge
                })
            # value bet
            elif VALUE_MIN <= odd <= VALUE_MAX:
                bets.append({
                    "home": home,
                    "away": away,
                    "pick": pick,
                    "odds": odd,
                    "stake": 100,
                    "status": "PENDING",
                    "league_key": game["sport_key"],
                    "league_name": game["sport_title"],
                    "date": game["commence_time"],
                    "type": "VALUE",
                    "edge": edge
                })
    return bets

# ================= MAIN =================
if __name__ == "__main__":
    leagues = [
        "basketball_nba",
        "basketball_euroleague",
        "americanfootball_nfl",
        "icehockey_nhl",
        "soccer_epl",
        "soccer_uefa_champs_league",
        "soccer_serie_a",
        "soccer_la_liga",
        "soccer_bundesliga",
        "soccer_ligue_one",
        "tennis_atp",
        "tennis_wta",
        "baseball_mlb",
        "basketball_ncaab",
        "americanfootball_cfl"
    ]

    all_bets = load_coupons()

    for league in leagues:
        offers = fetch_offers(league)
        bets = select_bets(offers)
        if bets:
            all_bets.extend(bets)
            send_msg(f"📌 Dodano {len(bets)} nowych kuponów z {league}")

    save_coupons(all_bets)
    print(f"[INFO] Dodano {len(all_bets)} kuponów łącznie")