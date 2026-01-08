import requests
import json
import os
from datetime import datetime, timedelta, timezone
from dateutil import parser

# ================= CONFIG =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS")

API_KEYS = [k for k in [
    os.getenv("ODDS_KEY"),
    os.getenv("ODDS_KEY_2"),
    os.getenv("ODDS_KEY_3")
] if k]

COUPONS_FILE = "coupons.json"
BANKROLL_FILE = "bankroll.json"
META_FILE = "meta.json"
START_BANKROLL = 100.0
MAX_HOURS_AHEAD = 60
MAX_PICKS_PER_DAY = 16
VALUE_THRESHOLD = 0.01  # niższy próg do testów
MIN_ODDS_SOCCER = 2.50
MIN_ODDS_NHL = 2.30

LEAGUES = [
    "icehockey_nhl",
    "basketball_nba",
    "soccer_epl",
    "soccer_england_championship",
    "soccer_poland_ekstraklasa",
    "soccer_germany_bundesliga",
    "soccer_uefa_champs_league"
]

LEAGUE_INFO = {
    "icehockey_nhl": {"name": "NHL", "flag": "🏒"},
    "basketball_nba": {"name": "NBA", "flag": "🏀"},
    "soccer_epl": {"name": "Premier League", "flag": "🏴"},
    "soccer_england_championship": {"name": "Championship", "flag": "🏴"},
    "soccer_poland_ekstraklasa": {"name": "Ekstraklasa", "flag": "🇵🇱"},
    "soccer_germany_bundesliga": {"name": "Bundesliga", "flag": "🇩🇪"},
    "soccer_uefa_champs_league": {"name": "Champions League", "flag": "🏆"}
}

# ================= FILE UTILS =================
def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

# ================= BANKROLL =================
def ensure_bankroll_file():
    if not os.path.exists(BANKROLL_FILE):
        save_json(BANKROLL_FILE, {"bankroll": START_BANKROLL, "peak": START_BANKROLL})

def load_bankroll():
    data = load_json(BANKROLL_FILE, {"bankroll": START_BANKROLL, "peak": START_BANKROLL})
    return data.get("bankroll", START_BANKROLL), data.get("peak", START_BANKROLL)

def save_bankroll(bankroll, peak=None):
    if peak is None:
        _, peak = load_bankroll()
    peak = max(bankroll, peak)
    save_json(BANKROLL_FILE, {"bankroll": round(bankroll,2), "peak": round(peak,2)})

# ================= TELEGRAM =================
def send_msg(text, target="types"):
    chat_id = T_CHAT_RESULTS if target == "results" else T_CHAT
    if not T_TOKEN or not chat_id:
        print("Brak tokena lub chat_id, nie wysyłam wiadomości")
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            },
            timeout=10
        )
    except Exception as e:
        print("Błąd wysyłania wiadomości:", e)

# ================= ODDS =================
def no_vig_probs(odds):
    inv = {k: 1/v for k,v in odds.items() if v}
    s = sum(inv.values())
    return {k: v/s for k,v in inv.items()}

def generate_pick(match):
    h_o = match["odds"]["home"]
    a_o = match["odds"]["away"]
    d_o = match["odds"].get("draw")

    if match["league"] == "icehockey_nhl":
        probs = no_vig_probs({"home": h_o, "away": a_o})
        p = {match["home"]: probs["home"], match["away"]: probs["away"]}
        min_odds = MIN_ODDS_NHL
    else:
        probs = no_vig_probs({"home": h_o, "away": a_o, "draw": d_o})
        p = {match["home"]: probs["home"], match["away"]: probs["away"], "Remis": probs.get("draw",0)*0.9}
        min_odds = MIN_ODDS_SOCCER

    best = None
    for sel, prob in p.items():
        odds = h_o if sel==match["home"] else a_o if sel==match["away"] else d_o
        edge = prob - (1/odds) if odds else 0
        print(f"DEBUG: {match['home']} vs {match['away']} - {sel}: odds={odds}, edge={edge:.4f}")
        if odds and odds>=min_odds and edge >= VALUE_THRESHOLD:
            if not best or edge > best["val"]:
                best = {"sel": sel, "odds": odds, "val": edge}
    if best:
        print(f"DEBUG: Wybrano typ: {best}")
    else:
        print("DEBUG: Brak typu spełniającego próg VALUE_THRESHOLD")
    return best

# ================= RUN =================
def run():
    ensure_bankroll_file()
    coupons = load_json(COUPONS_FILE, [])
    bankroll, peak = load_bankroll()

    now = datetime.now(timezone.utc)
    for league in LEAGUES:
        for key in API_KEYS:
            try:
                r = requests.get(
                    f"https://api.the-odds-api.com/v4/sports/{league}/odds",
                    params={"apiKey": key, "markets":"h2h","regions":"eu"},
                    timeout=10
                )
                if r.status_code != 200:
                    print(f"{league} - Błąd API: {r.status_code}")
                    continue
                data = r.json()
                print(f"{league} - liczba meczów pobranych z API: {len(data)}")

                for e in data:
                    dt = parser.isoparse(e["commence_time"])
                    if not (now <= dt <= now + timedelta(hours=MAX_HOURS_AHEAD)):
                        print(f"DEBUG: Mecz {e['home_team']} vs {e['away_team']} poza MAX_HOURS_AHEAD")
                        continue

                    odds = {}
                    for bm in e.get("bookmakers", []):
                        for m in bm.get("markets", []):
                            if m["key"]=="h2h":
                                for o in m.get("outcomes", []):
                                    odds[o["name"]] = max(odds.get(o["name"],0), o["price"])

                    print(f"DEBUG: {e['home_team']} vs {e['away_team']} - odds: {odds}")

                    pick = generate_pick({
                        "home": e["home_team"],
                        "away": e["away_team"],
                        "league": league,
                        "odds": {
                            "home": odds.get(e["home_team"]),
                            "away": odds.get(e["away_team"]),
                            "draw": odds.get("Draw")
                        }
                    })
                break
            except Exception as ex:
                print(f"DEBUG: Błąd przy pobieraniu {league}: {ex}")

if __name__ == "__main__":
    run()