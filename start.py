import requests, json, os, sys
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

START_BANKROLL = 10000.0
BANKROLL_FILE = "bankroll.json"
COUPONS_FILE = "coupons.json"
STATE_FILE = "state.json"

MAX_HOURS_AHEAD = 72
VALUE_THRESHOLD = 0.005
ODDS_MIN = 1.5
ODDS_MAX = 10.0
MAX_BETS_PER_DAY = 5

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
        print(f"[DEBUG] Telegram skipped: {txt}")
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
            json={"chat_id": chat, "text": txt, "parse_mode": "HTML"},
            timeout=10
        )
    except Exception as e:
        print(f"[DEBUG] Telegram error: {e}")

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
    if len(odds_list) < 2:
        return None
    mx, mn = max(odds_list), min(odds_list)
    if (mx - mn) / mx > 0.15:
        return None
    return mx

# ================= REPORT =================
def daily_report():
    """
    Wysyła codzienny raport do Telegrama, nawet jeśli nie ma nowych typów.
    """
    coupons = load_json(COUPONS_FILE, [])
    bankroll = load_bankroll()
    now = datetime.now(timezone.utc)

    msg = f"📊 <b>DAILY REPORT • {now.date()}</b>\n💰 Bankroll: {round(bankroll,2)} PLN\n\n"

    if not coupons:
        msg += "Brak typów do raportu."
        send_msg(msg, target="results")
        print(msg)
        return

    leagues = defaultdict(lambda: {"won":0,"lost":0,"profit":0.0,"total":0, "coupons":[]})

    # Grupowanie kuponów per liga
    for c in coupons:
        league = c.get("league", "unknown")
        leagues[league]["total"] += 1
        leagues[league]["coupons"].append(c)
        if c["status"] == "won":
            leagues[league]["won"] += 1
            leagues[league]["profit"] += c["stake"]*(c["odds"]-1)
        elif c["status"] == "lost":
            leagues[league]["lost"] += 1
            leagues[league]["profit"] -= c["stake"]

    # Tworzenie raportu per ligę
    for league, data in leagues.items():
        total = data["total"]
        won = data["won"]
        lost = data["lost"]
        profit = data["profit"]
        hit_rate = (won/total*100) if total>0 else 0
        blocks = int((hit_rate/100)*8)
        trend = "🔥" if profit>0 else "❌"
        league_name = league.upper()
        # Emoji dla lig
        if "nba" in league.lower():
            league_name = "🏀 NBA"
        elif "nhl" in league.lower():
            league_name = "🏒 NHL"
        elif "epl" in league.lower():
            league_name = "⚽ EPL"

        msg += f"{trend} {league_name} | Typy: {total} | Wygrane: {won} | Przegrane: {lost} | Hit rate: {int(hit_rate)}%\n"
        msg += "█"*blocks + "░"*(8-blocks) + f" | Zysk/Strata: {profit:.2f} PLN\n\n"

    # Najważniejsze mecze dnia (ostatnie 5 kuponów)
    msg += "🏟️ Najważniejsze mecze dnia:\n"
    last_coupons = coupons[-5:] if len(coupons)>=5 else coupons
    for c in last_coupons:
        status_icon = "✅" if c["status"]=="won" else "❌" if c["status"]=="lost" else "⏳"
        msg += f"\t• {c['home']} vs {c['away']} | Typ: {c['pick']} | Stawka: {c['stake']:.2f} PLN | {status_icon}\n"

    print("[DEBUG] Daily report:\n", msg)
    send_msg(msg, target="results")

# ================= RUN =================
def run():
    now = datetime.now(timezone.utc)
    bankroll = load_bankroll()
    coupons = load_json(COUPONS_FILE, [])
    state = load_state()

    if bankroll > state["ath"]:
        state["ath"] = bankroll
    if bankroll >= START_BANKROLL * 1.5:
        state["mode"] = "ULTRA"
    if state["mode"] == "ULTRA" and bankroll < state["ath"] * 0.8:
        state["mode"] = "AGGRESSIVE"
    save_state(state)

    KELLY = 0.5 if state["mode"]=="AGGRESSIVE" else 0.75
    MAX_PCT = 0.05 if state["mode"]=="AGGRESSIVE" else 0.06
    mode_icon = "⚔️ AGGRESSIVE" if state["mode"]=="AGGRESSIVE" else "🔥 ULTRA"

    daily_bets = 0
    total_events_checked = 0  # Nowy licznik meczów

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
                    total_events_checked += 1
                    dt = parser.isoparse(e["commence_time"])
                    if not (now <= dt <= now + timedelta(hours=MAX_HOURS_AHEAD)):
                        continue

                    odds_map = defaultdict(list)
                    for bm in e["bookmakers"]:
                        for m in bm["markets"]:
                            if m["key"] != "h2h": continue
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

                        if any(c["home"]==e["home_team"] and c["away"]==e["away_team"] and c["status"]=="pending" for c in coupons):
                            continue

                        stake = calc_kelly(bankroll, o, edge, KELLY, MAX_PCT)
                        if stake <= 0 or bankroll < stake:
                            continue

                        bankroll -= stake
                        save_bankroll(bankroll)

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
            except Exception as e:
                print(f"[DEBUG] Błąd API {league}: {e}")
                continue

    print(f"[DEBUG] Łącznie sprawdzonych meczów: {total_events_checked}")
    save_json(COUPONS_FILE, coupons)
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
                    if not m.get("completed"): continue
                    if m["home_team"] != c["home"] or m["away_team"] != c["away"]: continue

                    scores = {s["name"]: int(s["score"]) for s in m.get("scores", [])}
                    winner = c["home"] if scores[c["home"]] > scores[c["away"]] else c["away"]

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
    daily_report()

# ================= MAIN =================
if __name__ == "__main__":
    if "--results" in sys.argv:
        check_results()
    elif "--report" in sys.argv:
        daily_report()
    else:
        run()