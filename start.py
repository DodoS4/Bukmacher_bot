import requests, json, os, sys
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from dateutil import parser

# ================= CONFIG =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS")

# 5 KLUCZY API
API_KEYS = [k for k in [
    os.getenv("ODDS_KEY"),
    os.getenv("ODDS_KEY_2"),
    os.getenv("ODDS_KEY_3"),
    os.getenv("ODDS_KEY_4"),
    os.getenv("ODDS_KEY_5")
] if k]

START_BANKROLL = 10000.0
BANKROLL_FILE = "bankroll.json"
COUPONS_FILE = "coupons.json"
STATE_FILE = "state.json"

MAX_HOURS_AHEAD = 48
VALUE_THRESHOLD = 0.045
ODDS_MIN = 2.20
ODDS_MAX = 3.50
MAX_BETS_PER_DAY = 5

# ================= LIGI =================
LEAGUES = [
    "basketball_nba",
    "icehockey_nhl",
    "soccer_epl",
    "soccer_germany_bundesliga",
    "soccer_italy_serie_a"
]

EDGE_MULTIPLIER = {
    "basketball_nba": 0.85,
    "icehockey_nhl": 0.90,
    "soccer_epl": 0.70,
    "soccer_germany_bundesliga": 0.65,
    "soccer_italy_serie_a": 0.60
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
        json.dump(data, f, indent=2)

# ================= BANKROLL =================
def load_bankroll():
    data = load_json(BANKROLL_FILE, None)
    if not data:
        save_json(BANKROLL_FILE, {"bankroll": START_BANKROLL})
        return START_BANKROLL
    return data["bankroll"]

def save_bankroll(val):
    save_json(BANKROLL_FILE, {"bankroll": round(val, 2)})

# ================= STATE =================
def load_state():
    return load_json(STATE_FILE, {"ath": load_bankroll(), "mode": "AGGRESSIVE"})

def save_state(state):
    save_json(STATE_FILE, state)

# ================= TELEGRAM =================
def send_msg(txt, target="types"):
    chat = T_CHAT_RESULTS if target == "results" else T_CHAT
    if not T_TOKEN or not chat:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
            json={"chat_id": chat, "text": txt, "parse_mode": "HTML"},
            timeout=10
        )
    except:
        pass

# ================= KELLY =================
def calc_kelly(bankroll, odds, edge, kelly_frac, max_pct):
    if edge <= 0 or odds <= 1:
        return 0.0
    k = (edge / (odds - 1)) * kelly_frac
    stake = bankroll * k
    stake = max(10.0, stake)
    stake = min(stake, bankroll * max_pct)
    return round(stake, 2)

# ================= VALUE =================
def no_vig_probs(odds):
    inv = {k: 1/v for k, v in odds.items() if v}
    s = sum(inv.values())
    return {k: v/s for k, v in inv.items()}

def consensus_odds(odds_list):
    if len(odds_list) < 5:
        return None
    mx, mn = max(odds_list), min(odds_list)
    if (mx - mn) / mx > 0.08:
        return None
    return mx

# ================= DAILY REPORT =================
def daily_report():
    coupons = load_json(COUPONS_FILE, [])
    bankroll = load_bankroll()
    now = datetime.now(timezone.utc)
    
    report = defaultdict(lambda: {"bets":0, "won":0, "lost":0, "profit":0.0, "edges":[]})
    
    for c in coupons:
        if c.get("status") not in ("won","lost"):
            continue
        league = c["league"]
        report[league]["bets"] += 1
        if c["status"] == "won":
            report[league]["won"] += 1
            report[league]["profit"] += c["stake"]*(c["odds"]-1)
        else:
            report[league]["lost"] += 1
            report[league]["profit"] -= c["stake"]
        report[league]["edges"].append(round((c["odds"]-1)/c["stake"],3))
    
    msg = f"📊 <b>DAILY REPORT • {now.date()}</b>\n💰 Bankroll: {round(bankroll,2)} PLN\n\n"

    for league, data in report.items():
        if data["bets"] == 0:
            continue
        win_rate = round(data["won"]/data["bets"]*100,1)
        avg_edge = round(sum(data["edges"])/len(data["edges"])*100,2) if data["edges"] else 0
        msg += (
            f"🏆 {league} | Typów: {data['bets']} | "
            f"🟢 Wygrane: {data['won']} | 🔴 Przegrane: {data['lost']} | "
            f"💎 CLV: {avg_edge}% | 🤑 Zysk: {round(data['profit'],2)} PLN | "
            f"🎯 Hit-rate: {win_rate}%\n"
        )
    send_msg(msg, target="results")

# ================= RUN =================
def run():
    now = datetime.now(timezone.utc)
    hour = now.hour

    # OFF-PEAK HOURS (02:00–08:00 CET)
    if 2 <= hour <= 8:
        send_msg("⏸️ OFF-PEAK HOURS – bot wstrzymany", "results")
        return

    bankroll = load_bankroll()
    coupons = load_json(COUPONS_FILE, [])
    state = load_state()

    # ATH update
    if bankroll > state["ath"]:
        state["ath"] = bankroll

    # MODE SWITCH
    if bankroll >= START_BANKROLL * 1.5:
        state["mode"] = "ULTRA"
    if state["mode"] == "ULTRA" and bankroll < state["ath"] * 0.8:
        state["mode"] = "AGGRESSIVE"
    save_state(state)

    if state["mode"] == "ULTRA":
        KELLY = 0.75
        MAX_PCT = 0.06
        mode_icon = "🔥 ULTRA"
    else:
        KELLY = 0.5
        MAX_PCT = 0.05
        mode_icon = "⚔️ AGGRESSIVE"

    daily_bets = 0

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

                    odds_map = defaultdict(list)
                    for bm in e["bookmakers"]:
                        for m in bm["markets"]:
                            if m["key"] != "h2h":
                                continue
                            for o in m["outcomes"]:
                                odds_map[o["name"]].append(o["price"])

                    odds = {}
                    for name, lst in odds_map.items():
                        val = consensus_odds(lst)
                        if val and ODDS_MIN <= val <= ODDS_MAX:
                            odds[name] = val

                    if len(odds) < 2:
                        continue

                    probs = no_vig_probs(odds)
                    for sel, prob in probs.items():
                        o = odds[sel]
                        edge = (prob - 1/o) * EDGE_MULTIPLIER.get(league, 1)
                        if edge < VALUE_THRESHOLD:
                            continue

                        current_bankroll = load_bankroll()
                        stake = calc_kelly(current_bankroll, o, edge, KELLY, MAX_PCT)
                        if stake <= 0 or current_bankroll < stake:
                            continue

                        current_bankroll -= stake
                        save_bankroll(current_bankroll)

                        coupons.append({
                            "league": league,
                            "home": e["home_team"],
                            "away": e["away_team"],
                            "pick": sel,
                            "odds": o,
                            "stake": stake,
                            "status": "pending"
                        })

                        send_msg(
                            f"{mode_icon} <b>VALUE BET</b>\n"
                            f"{e['home_team']} vs {e['away_team']}\n"
                            f"🎯 {sel}\n"
                            f"📈 {o}\n"
                            f"💎 Edge: {round(edge*100,2)}%\n"
                            f"💰 {stake} PLN"
                        )

                        daily_bets += 1
                        if daily_bets >= MAX_BETS_PER_DAY:
                            break
                    if daily_bets >= MAX_BETS_PER_DAY:
                        break
                break
            except:
                continue

    save_json(COUPONS_FILE, coupons)
    # AUTO REPORT codzienny po rundzie
    daily_report()

# ================= RESULTS =================
def check_results():
    bankroll = load_bankroll()
    coupons = load_json(COUPONS_FILE, [])

    for c in coupons:
        if c["status"] != "pending":
            continue

        for key in API_KEYS:
            try:
                r = requests.get(
                    f"https://api.the-odds-api.com/v4/sports/{c['league']}/scores",
                    params={"apiKey": key, "daysFrom": 3},
                    timeout=10
                )
                if r.status_code != 200:
                    continue

                for m in r.json():
                    if not m.get("completed"):
                        continue
                    if m["home_team"] != c["home"] or m["away_team"] != c["away"]:
                        continue

                    scores = {s["name"]: int(s["score"]) for s in m.get("scores", [])}
                    winner = (
                        c["home"] if scores[c["home"]] > scores[c["away"]]
                        else c["away"]
                    )

                    if winner == c["pick"]:
                        profit = c["stake"] * (c["odds"] - 1)
                        bankroll += profit
                        c["status"] = "won"
                        send_msg(f"✅ WYGRANA {c['home']} vs {c['away']} | +{round(profit,2)} PLN", "results")
                    else:
                        c["status"] = "lost"
                        send_msg(f"❌ PRZEGRANA {c['home']} vs {c['away']} | -{c['stake']} PLN", "results")

                    save_bankroll(bankroll)
                break
            except:
                continue

    save_json(COUPONS_FILE, coupons)

# ================= MAIN =================
if __name__ == "__main__":
    if "--results" in sys.argv:
        check_results()
    elif "--report" in sys.argv:
        daily_report()
    else:
        run()