import requests
import json
import os
import random
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
MAX_PICKS_PER_DAY = 15

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

DYNAMIC_FORMS = {}

# ================= UTILS =================
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

def calc_kelly_stake(bankroll, odds, edge, kelly_frac):
    if edge <= 0 or odds <= 1:
        return 0.0
    b = odds - 1
    kelly = edge / b
    stake = bankroll * kelly * kelly_frac
    stake = max(3.0, stake)
    stake = min(stake, bankroll * 0.05)
    return round(stake, 2)

# ================= FORMS =================
def fetch_forms():
    forms = {}
    for league in LEAGUES:
        for key in API_KEYS:
            try:
                r = requests.get(
                    f"https://api.the-odds-api.com/v4/sports/{league}/scores",
                    params={"apiKey": key, "daysFrom": 14},
                    timeout=10
                )
                if r.status_code != 200:
                    continue
                for m in r.json():
                    if not m.get("completed"):
                        continue
                    h, a = m["home_team"], m["away_team"]
                    scores = {s["name"]: int(s["score"]) for s in m.get("scores", [])}
                    hs, as_ = scores.get(h, 0), scores.get(a, 0)
                    forms.setdefault(h, []).append(1 if hs > as_ else 0.5 if hs == as_ else 0)
                    forms.setdefault(a, []).append(1 if as_ > hs else 0.5 if hs == as_ else 0)
                break
            except:
                continue
    return forms

def team_form(team):
    res = DYNAMIC_FORMS.get(team, [])
    if not res:
        return 0.5
    weights = [1, 1.1, 1.2, 1.3, 1.4][-len(res):]
    return sum(r*w for r, w in zip(res, weights)) / sum(weights)

# ================= PROBABILITIES =================
def no_vig_probs(odds):
    inv = {k: 1/v for k, v in odds.items() if v}
    s = sum(inv.values())
    return {k: v/s for k, v in inv.items()}

def generate_pick(match):
    h_o, a_o, d_o = match["odds"]["home"], match["odds"]["away"], match["odds"].get("draw")

    if match["league"] == "icehockey_nhl":
        probs = no_vig_probs({"home": h_o, "away": a_o})
        p_h, p_a, p_d = probs["home"], probs["away"], 0
        min_odds = MIN_ODDS_NHL
    else:
        probs = no_vig_probs({"home": h_o, "away": a_o, "draw": d_o})
        p_h, p_a, p_d = probs["home"], probs["away"], probs.get("draw", 0)
        min_odds = MIN_ODDS_SOCCER

    f_h, f_a = team_form(match["home"]), team_form(match["away"])

    final = {
        match["home"]: 0.15*f_h + 0.85*p_h,
        match["away"]: 0.15*f_a + 0.85*p_a
    }
    if d_o:
        final["Remis"] = p_d * 0.9

    opts = []
    for sel, prob in final.items():
        odds = h_o if sel == match["home"] else a_o if sel == match["away"] else d_o
        if odds and odds >= min_odds:
            val = prob - (1/odds)
            if val >= VALUE_THRESHOLD:
                opts.append({"sel": sel, "odds": odds, "val": val})

    return max(opts, key=lambda x: x["val"]) if opts else None

# ================= PERFORMANCE =================
def rolling_perf(coupons, n=50):
    recent = [c for c in coupons if c["status"] in ("won", "lost")][-n:]
    if len(recent) < 20:
        return 0
    profit = sum(c["win_val"] if c["status"]=="won" else -c["stake"] for c in recent)
    staked = sum(c["stake"] for c in recent)
    return profit / staked if staked else 0

def league_roi(coupons):
    stats = {}
    for c in coupons:
        if c["status"] not in ("won","lost"):
            continue
        s = stats.setdefault(c["league"], {"p":0,"s":0,"n":0})
        s["n"] += 1
        s["s"] += c["stake"]
        s["p"] += c["win_val"] if c["status"]=="won" else -c["stake"]
    return {k:v["p"]/v["s"] for k,v in stats.items() if v["n"]>=25}

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
                    if c["status"]!="pending" or c["league"]!=league:
                        continue
                    m = next((x for x in r.json()
                        if x["home_team"]==c["home"]
                        and x["away_team"]==c["away"]
                        and x.get("completed")), None)
                    if not m:
                        continue

                    scores = {s["name"]: int(s["score"]) for s in m.get("scores", [])}
                    hs, as_ = scores.get(c["home"],0), scores.get(c["away"],0)
                    winner = c["home"] if hs>as_ else c["away"] if as_>hs else "Remis"

                    if winner == c["picked"]:
                        profit = round(c["stake"]*(c["odds"]-1),2)
                        bankroll += profit
                        c["status"]="won"
                        c["win_val"]=profit
                    else:
                        c["status"]="lost"
                        c["win_val"]=0
                break
            except:
                continue

    save_bankroll(bankroll)
    save_json(COUPONS_FILE, coupons)

# ================= RUN =================
def run():
    global DYNAMIC_FORMS
    check_results()
    DYNAMIC_FORMS = fetch_forms()

    coupons = load_json(COUPONS_FILE, [])
    bankroll = load_bankroll()
    today = str(datetime.now(timezone.utc).date())

    sent_today = [c for c in coupons if c.get("sent_date")==today]
    if len(sent_today) >= MAX_PICKS_PER_DAY:
        return

    perf = rolling_perf(coupons)
    KELLY = 0.25 if perf>0 else 0.18 if perf>-0.05 else 0.12
    bad_leagues = [l for l,r in league_roi(coupons).items() if r<-0.04]

    all_picks = []

    for league in LEAGUES:
        if league in bad_leagues:
            continue
        for key in API_KEYS:
            try:
                r = requests.get(
                    f"https://api.the-odds-api.com/v4/sports/{league}/odds",
                    params={"apiKey": key, "markets":"h2h", "regions":"eu"},
                    timeout=10
                )
                if r.status_code!=200:
                    continue

                for e in r.json():
                    m_dt = parser.isoparse(e["commence_time"])
                    if m_dt > datetime.now(timezone.utc)+timedelta(hours=MAX_HOURS_AHEAD):
                        continue

                    odds = {}
                    for bm in e["bookmakers"]:
                        for m in bm["markets"]:
                            if m["key"]=="h2h":
                                for o in m["outcomes"]:
                                    odds[o["name"]] = max(odds.get(o["name"],0), o["price"])

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
                        pick["event"]=e
                        all_picks.append(pick)
                break
            except:
                continue

    for p in sorted(all_picks, key=lambda x:x["val"], reverse=True):
        if len(sent_today)>=MAX_PICKS_PER_DAY:
            break
        stake = calc_kelly_stake(bankroll, p["odds"], p["val"], KELLY)
        if stake<=0:
            continue

        bankroll -= stake
        save_bankroll(bankroll)

        e = p["event"]
        coupons.append({
            "home": e["home_team"],
            "away": e["away_team"],
            "picked": p["sel"],
            "odds": p["odds"],
            "stake": stake,
            "league": p["event"]["sport_key"],
            "status": "pending",
            "win_val": 0,
            "sent_date": today
        })

        sent_today.append(True)

        send_msg(
            f"🎯 <b>VALUE BET</b>\n"
            f"{e['home_team']} vs {e['away_team']}\n"
            f"Typ: <b>{p['sel']}</b>\n"
            f"Kurs: <b>{p['odds']}</b>\n"
            f"Edge: <b>{round(p['val']*100,2)}%</b>\n"
            f"Stawka: <b>{stake} PLN</b>"
        )

    save_json(COUPONS_FILE, coupons)

if __name__ == "__main__":
    run()