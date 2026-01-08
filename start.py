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
MAX_HOURS_AHEAD = 30  # mecze max 30h na przód
MAX_PICKS_PER_DAY = 16
VALUE_THRESHOLD = 0.035
MIN_ODDS_SOCCER = 2.50
MIN_ODDS_NHL = 2.30

# Drawdown guard
DRAWDOWN_THRESHOLD = 0.8  # 80% of peak

# Auto-disable lig
ROI_DISABLE_THRESHOLD = -0.05  # -5%
MIN_BETS_FOR_DISABLE = 20

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
        p = {match["home"]: probs["home"], match["away"]: probs["away"]}
        min_odds = MIN_ODDS_NHL
    else:
        probs = no_vig_probs({"home": h_o, "away": a_o, "draw": d_o})
        p = {match["home"]: probs["home"], match["away"]: probs["away"], "Remis": probs.get("draw",0)*0.9}
        min_odds = MIN_ODDS_SOCCER

    best = None
    for sel, prob in p.items():
        odds = h_o if sel == match["home"] else a_o if sel == match["away"] else d_o
        if odds and odds >= min_odds:
            edge = prob - (1/odds)
            if edge >= VALUE_THRESHOLD:
                if not best or edge > best["val"]:
                    best = {"sel": sel, "odds": odds, "val": edge}
    return best

# ================= KELLY / STAKE =================
def adaptive_kelly(bankroll, odds, edge, league, peak):
    kelly_frac = 0.25
    meta = load_json(META_FILE, {})
    league_roi = meta.get("league_roi", {}).get(league, 0)
    if league_roi > 0.05:
        kelly_frac = 0.35
    elif league_roi < 0:
        kelly_frac = 0.15
    if bankroll < peak * DRAWDOWN_THRESHOLD:
        kelly_frac *= 0.5
    if edge <=0 or odds <=1:
        return 0.0
    stake = bankroll * (edge / (odds - 1)) * kelly_frac
    return round(min(max(stake, 3.0), bankroll*0.05),2)

# ================= FORMAT =================
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

# ================= RESULTS =================
def check_results():
    coupons = load_json(COUPONS_FILE, [])
    bankroll, peak = load_bankroll()

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
                    hs, as_ = scores.get(c["home"],0), scores.get(c["away"],0)
                    winner = c["home"] if hs>as_ else c["away"] if as_>hs else "Remis"

                    if winner == c["picked"]:
                        profit = round(c["stake"]*(c["odds"]-1),2)
                        bankroll += profit
                        c["status"] = "won"
                        c["win_val"] = profit
                    else:
                        bankroll -= c["stake"]
                        c["status"] = "lost"
                        c["win_val"] = 0
                break
            except:
                continue

    save_bankroll(bankroll, peak)
    save_json(COUPONS_FILE, coupons)

# ================= STATS =================
def league_stats(coupons, start, end):
    stats = {}
    for c in coupons:
        if c["status"] not in ("won","lost"):
            continue
        sent = c.get("sent_date")
        if not sent or not (start <= sent <= end):
            continue
        lg = c["league"]
        s = stats.setdefault(lg, {"stake":0,"profit":0,"cnt":0})
        s["stake"] += c["stake"]
        s["profit"] += c["win_val"] if c["status"]=="won" else -c["stake"]
        s["cnt"] +=1
    return stats

def send_summary(stats, title):
    if not stats:
        return
    msg = f"{title}\n━━━━━━━━━━━━━━━━━━\n"
    for lg, s in sorted(stats.items(), key=lambda x: x[1]["profit"], reverse=True):
        roi = (s["profit"]/s["stake"]*100) if s["stake"] else 0
        info = LEAGUE_INFO.get(lg, {"name":lg,"flag":"🎯"})
        msg += f"{info['flag']} {info['name']}: <b>{round(s['profit'],2)} PLN</b> | ROI {round(roi,2)}% ({s['cnt']})\n"
    send_msg(msg,"results")

# ================= RUN =================
def run():
    ensure_bankroll_file()
    check_results()

    coupons = load_json(COUPONS_FILE, [])
    bankroll, peak = load_bankroll()
    meta = load_json(META_FILE, {})

    today = datetime.now(timezone.utc).date().isoformat()
    # Daily summary
    if meta.get("last_daily") != today:
        stats = league_stats(coupons, today, today)
        send_summary(stats,f"📊 <b>PODSUMOWANIE DZIENNE • {today}</b>")
        meta["last_daily"] = today

    # Weekly summary
    year, week, _ = datetime.now(timezone.utc).isocalendar()
    wk = f"{year}-W{week}"
    if meta.get("last_weekly") != wk:
        start = (datetime.now(timezone.utc) - timedelta(days=7)).date().isoformat()
        stats = league_stats(coupons, start, today)
        send_summary(stats,f"🏆 <b>PODSUMOWANIE TYGODNIOWE • {wk}</b>")
        meta["last_weekly"] = wk

    # Save meta
    save_json(META_FILE, meta)

if __name__ == "__main__":
    run()