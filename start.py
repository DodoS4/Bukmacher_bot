import requests
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from dateutil import parser

# ================= CONFIG =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS")

API_KEYS = [k for k in [
    os.getenv("ODDS_KEY"),
    os.getenv("ODDS_KEY_2"),
    os.getenv("ODDS_KEY_3"),
    os.getenv("ODDS_KEY_4"),
    os.getenv("ODDS_KEY_5")
] if k]

COUPONS_FILE = "coupons.json"
BANKROLL_FILE = "bankroll.json"
START_BANKROLL = 100.0

# ===== TRYB TESTOWY =====
MAX_HOURS_AHEAD = 72
VALUE_THRESHOLD = 0.01
KELLY_FRACTION = 0.10

# ================= LIGI =================
LEAGUES = [
    "icehockey_nhl",
    "basketball_nba",
    "soccer_epl",
    "soccer_spain_la_liga",
    "soccer_germany_bundesliga",
    "soccer_italy_serie_a",
    "soccer_poland_ekstraklasa",
    "soccer_uefa_champs_league"
]

LEAGUE_INFO = {
    "icehockey_nhl": {"name": "NHL", "flag": "🏒"},
    "basketball_nba": {"name": "NBA", "flag": "🏀"},
    "soccer_epl": {"name": "Premier League", "flag": "⚽"},
    "soccer_spain_la_liga": {"name": "La Liga", "flag": "🇪🇸"},
    "soccer_germany_bundesliga": {"name": "Bundesliga", "flag": "🇩🇪"},
    "soccer_italy_serie_a": {"name": "Serie A", "flag": "🇮🇹"},
    "soccer_poland_ekstraklasa": {"name": "Ekstraklasa", "flag": "🇵🇱"},
    "soccer_uefa_champs_league": {"name": "Champions League", "flag": "🏆"}
}

MIN_ODDS = {
    "icehockey_nhl": 1.80,
    "basketball_nba": 1.55,
    "soccer_epl": 2.0,
    "soccer_spain_la_liga": 2.0,
    "soccer_germany_bundesliga": 2.0,
    "soccer_italy_serie_a": 2.0,
    "soccer_poland_ekstraklasa": 2.0,
    "soccer_uefa_champs_league": 2.0
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
def load_bankroll():
    return load_json(BANKROLL_FILE, {}).get("bankroll", START_BANKROLL)

def save_bankroll(val):
    save_json(BANKROLL_FILE, {"bankroll": round(val, 2)})

def calc_kelly_stake(bankroll, odds, edge):
    if edge <= 0 or odds <= 1:
        return 0.0
    b = odds - 1
    kelly = edge / b
    stake = bankroll * kelly * KELLY_FRACTION
    stake = max(3.0, stake)
    stake = min(stake, bankroll * 0.05)
    return round(stake, 2)

# ================= TELEGRAM =================
def send_msg(text):
    if not T_TOKEN or not T_CHAT:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
            json={
                "chat_id": T_CHAT,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            },
            timeout=10
        )
    except:
        pass

# ================= HELPERS =================
def already_sent(coupons, home, away, league):
    for c in coupons:
        if c["home"] == home and c["away"] == away and c["league"] == league:
            return True
    return False

def no_vig_probs(odds):
    inv = {k: 1/v for k, v in odds.items() if v}
    s = sum(inv.values())
    return {k: v/s for k, v in inv.items()}

def format_time(dt):
    return dt.strftime("%d.%m.%Y • %H:%M UTC")

# ================= PICK =================
def generate_pick(match):
    h = match["odds"]["home"]
    a = match["odds"]["away"]
    d = match["odds"].get("draw")

    if match["league"] == "icehockey_nhl":
        probs = no_vig_probs({"home": h, "away": a})
        options = {
            match["home"]: (probs["home"], h),
            match["away"]: (probs["away"], a)
        }
    else:
        probs = no_vig_probs({"home": h, "away": a, "draw": d})
        options = {
            match["home"]: (probs["home"], h),
            match["away"]: (probs["away"], a),
            "Remis": (probs.get("draw", 0) * 0.9, d)
        }

    best = None
    min_odds = MIN_ODDS.get(match["league"], 2.0)

    for sel, (prob, odds) in options.items():
        if odds and odds >= min_odds:
            edge = prob - (1 / odds)
            if edge >= VALUE_THRESHOLD:
                if not best or edge > best["edge"]:
                    best = {"sel": sel, "odds": odds, "edge": edge}

    return best

# ================= RUN =================
def run():
    coupons = load_json(COUPONS_FILE, [])
    bankroll = load_bankroll()
    now = datetime.now(timezone.utc)
    all_picks = []

    for league in LEAGUES:
        for key in API_KEYS:
            try:
                r = requests.get(
                    f"https://api.the-odds-api.com/v4/sports/{league}/odds",
                    params={"apiKey": key, "markets": "h2h", "regions": "eu"},
                    timeout=10
                )
                if r.status_code != 200:
                    continue

                events = r.json()
                print(f"[DEBUG] {league}: {len(events)} meczów")

                for e in events:
                    dt = parser.isoparse(e["commence_time"])
                    if not (now <= dt <= now + timedelta(hours=MAX_HOURS_AHEAD)):
                        continue

                    if already_sent(coupons, e["home_team"], e["away_team"], league):
                        continue

                    odds = {}
                    for bm in e["bookmakers"]:
                        for m in bm["markets"]:
                            if m["key"] == "h2h":
                                for o in m["outcomes"]:
                                    odds[o["name"]] = max(odds.get(o["name"], 0), o["price"])

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

                    if pick:
                        all_picks.append((pick, e, dt, league))
                break
            except:
                continue

    for pick, e, dt, league in sorted(all_picks, key=lambda x: x[0]["edge"], reverse=True):
        stake = calc_kelly_stake(bankroll, pick["odds"], pick["edge"])
        if stake <= 0:
            continue

        bankroll -= stake
        save_bankroll(bankroll)

        coupons.append({
            "home": e["home_team"],
            "away": e["away_team"],
            "picked": pick["sel"],
            "odds": pick["odds"],
            "stake": stake,
            "league": league,
            "status": "pending",
            "sent_date": str(now.date())
        })

        info = LEAGUE_INFO.get(league, {"name": league, "flag": "🎯"})
        send_msg(
            f"{info['flag']} <b>TEST VALUE • {info['name']}</b>\n"
            f"{e['home_team']} vs {e['away_team']}\n"
            f"🕒 {format_time(dt)}\n"
            f"🎯 {pick['sel']} | Kurs: {pick['odds']}\n"
            f"💎 Edge: +{round(pick['edge']*100,2)}%\n"
            f"💰 Stawka: {stake} PLN"
        )

    save_json(COUPONS_FILE, coupons)

# ================= MAIN =================
if __name__ == "__main__":
    run()