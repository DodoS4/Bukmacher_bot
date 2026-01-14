import requests, json, os
from datetime import datetime, timezone

# ================= CONFIG =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")
API_KEYS = [os.getenv(f"ODDS_KEY{i}") for i in ["", "_2", "_3", "_4", "_5"]]
API_KEYS = [k for k in API_KEYS if k]
COUPONS_FILE = "coupons.json"
TAX_PL = 1.0  # bez podatku

# Ligi do pobrania
LEAGUES = [
    "basketball_nba", "basketball_euroleague", "icehockey_nhl",
    "soccer_epl", "soccer_serie_a", "soccer_laliga",
    "soccer_bundesliga", "soccer_ligue1", "basketball_mln",
    "icehockey_ngk", "soccer_champions_league",
    "soccer_eredivisie", "soccer_portugal", "basketball_wnba"
]

# ================= FUNCTIONS =================
def send_msg(txt):
    if not T_TOKEN or not T_CHAT: return
    try:
        requests.post(f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
                      json={"chat_id": T_CHAT, "text": txt, "parse_mode": "HTML"})
    except Exception as e:
        print(f"[ERROR] Telegram: {e}")

def load_coupons():
    if not os.path.exists(COUPONS_FILE): return []
    try:
        with open(COUPONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def save_coupons(coupons):
    with open(COUPONS_FILE, "w", encoding="utf-8") as f:
        json.dump(coupons, f, indent=2)

def fetch_odds(league_key):
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
    new_count = 0

    for league in LEAGUES:
        games = fetch_odds(league)
        if not games:
            print(f"[INFO] Brak danych dla ligi: {league}")
            continue

        for g in games:
            try:
                home = g["home_team"]
                away = g["away_team"]
                for outcome, odd in zip(["home", "away"], [g["bookmakers"][0]["markets"][0]["outcomes"][0]["price"], g["bookmakers"][0]["markets"][0]["outcomes"][1]["price"]]):
                    # Prosty filtr: value bet + pewniaki
                    if odd < 1.2 or odd > 15:  # od 1.2 do 15
                        continue

                    coupon = {
                        "home": home,
                        "away": away,
                        "pick": home if outcome=="home" else away,
                        "odds": odd,
                        "stake": 100,
                        "status": "PENDING",
                        "league": g.get("sport_title", league),
                        "league_key": league,
                        "date": g["commence_time"],
                        "edge": round((odd - 1) * 100 / 10, 2)  # prosta wartość edge
                    }
                    coupons.append(coupon)
                    txt = f"📌 Nowy typ: {coupon['home']} - {coupon['away']}\nTyp: {coupon['pick']} | Kurs: {coupon['odds']}"
                    send_msg(txt)
                    new_count += 1
            except: continue

    save_coupons(coupons)
    print(f"[INFO] Dodano {new_count} nowych kuponów")

# ================= MAIN =================
if __name__ == "__main__":
    generate_coupons()