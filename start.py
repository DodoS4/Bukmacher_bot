import requests
import json
import os
from datetime import datetime, timedelta, timezone
from dateutil import parser

# ================= KONFIGURACJA =================
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

MAX_HOURS_AHEAD = 90
MIN_HOURS_BEFORE = 2

CORE_EDGE = 0.09
SUPPORT_EDGE = 0.01

MAX_PICKS_DAILY = 5

LEAGUES = [
    "icehockey_nhl",
    "basketball_nba",
    "soccer_epl",
    "soccer_poland_ekstraklasa",
    "soccer_germany_bundesliga",
    "soccer_uefa_champs_league"
]

# ================= POMOCNICZE =================
def send_msg(text, target="types"):
    chat_id = T_CHAT_RESULTS if target == "results" else T_CHAT
    if not T_TOKEN or not chat_id:
        return
    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except:
        pass


def load_bankroll():
    if os.path.exists(BANKROLL_FILE):
        return json.load(open(BANKROLL_FILE)).get("bankroll", START_BANKROLL)
    return START_BANKROLL


def save_bankroll(val):
    json.dump({"bankroll": round(val, 2)}, open(BANKROLL_FILE, "w"))


def load_coupons():
    if os.path.exists(COUPONS_FILE):
        return json.load(open(COUPONS_FILE))
    return []


def save_coupons(coupons):
    json.dump(coupons[-2000:], open(COUPONS_FILE, "w"), indent=2)


# ================= KELLY =================
def adaptive_kelly(bankroll, odds, edge):
    if edge < SUPPORT_EDGE or odds <= 1:
        return 0

    if edge >= CORE_EDGE:
        kf = 0.20
    else:
        kf = 0.10

    stake = bankroll * kf * (edge / odds)
    stake = max(3, stake)
    stake = min(stake, bankroll * 0.05)
    return round(stake, 2)


# ================= BEST ODDS =================
def extract_best_odds(event):
    best = {}
    for bm in event.get("bookmakers", []):
        for m in bm.get("markets", []):
            if m["key"] != "h2h":
                continue
            for o in m["outcomes"]:
                name = o["name"]
                price = o["price"]
                if name not in best or price > best[name]:
                    best[name] = price
    return best


# ================= VALUE =================
def calc_value_probs(best_odds):
    inv = {k: 1/v for k, v in best_odds.items()}
    total = sum(inv.values())
    return {k: inv[k]/total for k in inv}


def generate_pick(event, probs):
    picks = []
    for team, odds in event["best_odds"].items():
        if odds < 2.0:
            continue
        edge = probs[team] - (1 / odds)
        if edge >= SUPPORT_EDGE:
            picks.append({
                "sel": team,
                "odds": odds,
                "edge": edge
            })
    if not picks:
        return None
    return max(picks, key=lambda x: x["edge"])


# ================= ROZLICZENIA =================
def check_results():
    coupons = load_coupons()
    bankroll = load_bankroll()

    for league in LEAGUES:
        for key in API_KEYS:
            r = requests.get(
                f"https://api.the-odds-api.com/v4/sports/{league}/scores",
                params={"apiKey": key, "daysFrom": 3},
                timeout=10
            )
            if r.status_code != 200:
                continue

            for match in r.json():
                if not match.get("completed"):
                    continue

                for c in coupons:
                    if c["status"] != "pending":
                        continue
                    if c["home"] != match["home_team"]:
                        continue

                    scores = {s["name"]: int(s["score"]) for s in match["scores"]}
                    hs = scores.get(c["home"], 0)
                    as_ = scores.get(c["away"], 0)

                    winner = c["home"] if hs > as_ else c["away"] if as_ > hs else "Draw"

                    if c["picked"] == winner:
                        bankroll += c["stake"] * (c["odds"] - 1)
                        c["status"] = "won"
                        icon = "✅"
                    else:
                        bankroll -= c["stake"]
                        c["status"] = "lost"
                        icon = "❌"

                    send_msg(
                        f"{icon} <b>ROZLICZENIE</b>\n"
                        f"{c['home']} vs {c['away']}\n"
                        f"Typ: {c['picked']}\n"
                        f"Stawka: {c['stake']} PLN",
                        "results"
                    )

            break

    save_bankroll(bankroll)
    save_coupons(coupons)


# ================= RUN =================
def run():
    check_results()

    bankroll = load_bankroll()
    coupons = load_coupons()
    now = datetime.now(timezone.utc)

    all_picks = []

    for league in LEAGUES:
        for key in API_KEYS:
            r = requests.get(
                f"https://api.the-odds-api.com/v4/sports/{league}/odds",
                params={"apiKey": key, "regions": "eu", "markets": "h2h"},
                timeout=10
            )
            if r.status_code != 200:
                continue

            for event in r.json():
                dt = parser.isoparse(event["commence_time"])
                if not (now + timedelta(hours=MIN_HOURS_BEFORE) <= dt <= now + timedelta(hours=MAX_HOURS_AHEAD)):
                    continue

                best_odds = extract_best_odds(event)
                if len(best_odds) < 2:
                    continue

                probs = calc_value_probs(best_odds)
                pick = generate_pick({"best_odds": best_odds}, probs)
                if not pick:
                    continue

                pick.update({
                    "home": event["home_team"],
                    "away": event["away_team"],
                    "league": league,
                    "time": event["commence_time"]
                })
                all_picks.append(pick)
            break

    core = [p for p in all_picks if p["edge"] >= CORE_EDGE]
    support = [p for p in all_picks if SUPPORT_EDGE <= p["edge"] < CORE_EDGE]

    final = core[:3] + support[:MAX_PICKS_DAILY - len(core)]
    final = final[:MAX_PICKS_DAILY]

    for p in final:
        stake = adaptive_kelly(bankroll, p["odds"], p["edge"])
        if stake <= 0:
            continue

        send_msg(
            f"💎 <b>VALUE BET</b>\n"
            f"{p['home']} vs {p['away']}\n"
            f"Typ: <b>{p['sel']}</b>\n"
            f"Kurs: {p['odds']}\n"
            f"Edge: +{round(p['edge']*100,2)}%\n"
            f"Stawka: {stake} PLN"
        )

        coupons.append({
            "home": p["home"],
            "away": p["away"],
            "picked": p["sel"],
            "odds": p["odds"],
            "stake": stake,
            "status": "pending",
            "date": p["time"],
            "league": p["league"]
        })

    save_coupons(coupons)


if __name__ == "__main__":
    run()