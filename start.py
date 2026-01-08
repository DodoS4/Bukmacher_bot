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
START_BANKROLL = 100.0

MAX_HOURS_AHEAD = 24
MAX_PICKS_PER_DAY = 9

VALUE_THRESHOLD = 0.035
CORE_EDGE = 0.06

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
        save_json(BANKROLL_FILE, {"bankroll": START_BANKROLL})

def load_bankroll():
    return load_json(BANKROLL_FILE, {}).get("bankroll", START_BANKROLL)

def save_bankroll(val):
    save_json(BANKROLL_FILE, {"bankroll": round(val, 2)})

def calc_kelly_stake(bankroll, odds, edge, kelly_frac):
    if edge <= 0 or odds <= 1:
        return 0.0
    b = odds - 1
    kelly = edge / b
    stake = bankroll * kelly * kelly_frac
    stake = max(3.0, stake)
    stake = min(stake, bankroll * 0.05)
    return round(stake, 2)

# ================= TELEGRAM =================
def send_msg(text, target="types"):
    chat_id = T_CHAT_RESULTS if target == "results" else T_CHAT
    if not T_TOKEN or not chat_id:
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
    except:
        pass

# ================= FORMAT UI =================
def format_match_time(dt):
    return dt.strftime("%d.%m.%Y • %H:%M UTC")

def format_value_card(league_key, home, away, dt, pick, odds, edge, stake):
    info = LEAGUE_INFO.get(league_key, {"name": league_key, "flag": "🎯"})
    tier = "A" if edge >= 0.08 else "B"
    return (
        f"{info['flag']} <b>VALUE BET • {info['name']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"<b>{home} vs {away}</b>\n"
        f"🕒 {format_match_time(dt)}\n\n"
        f"🎯 Typ: <b>{pick}</b>\n"
        f"📈 Kurs: <b>{odds}</b>\n"
        f"💎 Edge: <b>+{round(edge*100,2)}%</b>\n"
        f"🏷 Tier: <b>{tier}</b>\n"
        f"💰 Stawka: <b>{stake} PLN</b>"
    )

# ================= ODDS =================
def no_vig_probs(odds):
    inv = {k: 1/v for k, v in odds.items() if v}
    s = sum(inv.values())
    return {k: v/s for k, v in inv.items()}

def generate_pick(match):
    h_o = match["odds"]["home"]
    a_o = match["odds"]["away"]
    d_o = match["odds"].get("draw")

    if match["league"] == "icehockey_nhl":
        probs = no_vig_probs({"home": h_o, "away": a_o})
        p = {
            match["home"]: probs["home"],
            match["away"]: probs["away"]
        }
        min_odds = MIN_ODDS_NHL
    else:
        probs = no_vig_probs({"home": h_o, "away": a_o, "draw": d_o})
        p = {
            match["home"]: probs["home"],
            match["away"]: probs["away"],
            "Remis": probs.get("draw", 0) * 0.9
        }
        min_odds = MIN_ODDS_SOCCER

    best = None
    for sel, prob in p.items():
        odds = h_o if sel == match["home"] else a_o if sel == match["away"] else d_o
        if odds and odds >= min_odds:
            edge = prob - (1 / odds)
            if edge >= VALUE_THRESHOLD:
                if not best or edge > best["val"]:
                    best = {"sel": sel, "odds": odds, "val": edge}
    return best

# ================= RESULTS =================
def check_results():
    coupons = load_json(COUPONS_FILE, [])
    bankroll = load_bankroll()

    for league in LEAGUES:
        for key in API_KEYS:
            try:
                r = requests.get(
                    f"https://api.the-odds-api.com/v4/sports/{league}/scores",
                    params={"apiKey": key, "daysFrom": 3},
                    timeout=10
                )
                if r.status_code != 200:
                    continue

                for c in coupons:
                    if c["status"] != "pending" or c["league"] != league:
                        continue

                    m = next((x for x in r.json()
                        if x["home_team"] == c["home"]
                        and x["away_team"] == c["away"]
                        and x.get("completed")), None)

                    if not m:
                        continue

                    scores = {s["name"]: int(s["score"]) for s in m.get("scores", [])}
                    hs, as_ = scores.get(c["home"], 0), scores.get(c["away"], 0)
                    winner = c["home"] if hs > as_ else c["away"] if as_ > hs else "Remis"

                    if winner == c["picked"]:
                        profit = round(c["stake"] * (c["odds"] - 1), 2)
                        bankroll += profit
                        c["status"] = "won"
                        c["win_val"] = profit
                        icon = "✅"
                    else:
                        c["status"] = "lost"
                        c["win_val"] = 0
                        icon = "❌"

                    send_msg(
                        f"{icon} <b>ROZLICZENIE</b>\n"
                        f"{c['home']} vs {c['away']}\n"
                        f"Typ: {c['picked']} | Stawka: {c['stake']} PLN",
                        target="results"
                    )
                break
            except:
                continue

    save_bankroll(bankroll)
    save_json(COUPONS_FILE, coupons)

# ================= RUN =================
def run():
    check_results()

    coupons = load_json(COUPONS_FILE, [])
    bankroll = load_bankroll()

    now = datetime.now(timezone.utc)
    today = str(now.date())
    sent_today = [c for c in coupons if c.get("sent_date") == today]
    if len(sent_today) >= MAX_PICKS_PER_DAY:
        return

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

                for e in r.json():
                    dt = parser.isoparse(e["commence_time"])
                    if not (now <= dt <= now + timedelta(hours=MAX_HOURS_AHEAD)):
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

    for pick, e, dt, league in sorted(all_picks, key=lambda x: x[0]["val"], reverse=True):
        if len(sent_today) >= MAX_PICKS_PER_DAY:
            break

        stake = calc_kelly_stake(bankroll, pick["odds"], pick["val"], 0.25)
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
            "win_val": 0,
            "sent_date": today
        })
        sent_today.append(True)

        send_msg(
            format_value_card(
                league,
                e["home_team"],
                e["away_team"],
                dt,
                pick["sel"],
                pick["odds"],
                pick["val"],
                stake
            )
        )

    save_json(COUPONS_FILE, coupons)

if __name__ == "__main__":
    ensure_bankroll_file()
    run()