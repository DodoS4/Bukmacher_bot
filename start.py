import requests
import json
import os
from datetime import datetime, timedelta, timezone

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

MAX_HOURS_AHEAD = 48
MAX_PICKS_PER_DAY = 9

# ======= Progi kursów i edge =======
VALUE_THRESHOLD = 0.035  # ogólne ligii
MIN_ODDS_SOCCER = 2.50
MIN_ODDS_NHL = 2.30

# NBA osobny próg
MIN_ODDS_NBA = 1.9
MAX_ODDS_NBA = 2.35
VALUE_THRESHOLD_NBA = 0.02

LEAGUES = [
    "icehockey_nhl",
    "basketball_nba",
    "soccer_epl",
    "soccer_england_championship",
    "soccer_poland_ekstraklasa",
    "soccer_germany_bundesliga",
    "soccer_uefa_champs_league",
    "soccer_spain_la_liga",
    "soccer_italy_serie_a"
]

LEAGUE_INFO = {
    "icehockey_nhl": {"name": "NHL", "flag": "🏒"},
    "basketball_nba": {"name": "NBA", "flag": "🏀"},
    "soccer_epl": {"name": "Premier League", "flag": "🏴"},
    "soccer_england_championship": {"name": "Championship", "flag": "🏴"},
    "soccer_poland_ekstraklasa": {"name": "Ekstraklasa", "flag": "🇵🇱"},
    "soccer_germany_bundesliga": {"name": "Bundesliga", "flag": "🇩🇪"},
    "soccer_uefa_champs_league": {"name": "Champions League", "flag": "🏆"},
    "soccer_spain_la_liga": {"name": "La Liga", "flag": "🇪🇸"},
    "soccer_italy_serie_a": {"name": "Serie A", "flag": "🇮🇹"}
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

def calc_kelly_stake(bankroll, odds, edge, kelly_frac=0.25):
    if edge <= 0 or odds <= 1:
        return 0.0
    stake = bankroll * (edge / (odds - 1)) * kelly_frac
    return round(min(max(stake, 3.0), bankroll * 0.05), 2)

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

# ================= STATS =================
def league_stats(coupons, start, end):
    stats = {}
    for c in coupons:
        if c["status"] not in ("won", "lost", "pending"):
            continue
        if not (start <= c.get("sent_date", "") <= end):
            continue

        lg = c["league"]
        s = stats.setdefault(lg, {"stake": 0, "profit": 0, "cnt": 0, "pending": 0})
        if c["status"] == "won":
            s["stake"] += c["stake"]
            s["profit"] += c["win_val"]
            s["cnt"] += 1
        elif c["status"] == "lost":
            s["stake"] += c["stake"]
            s["profit"] -= c["stake"]
            s["cnt"] += 1
        elif c["status"] == "pending":
            s["pending"] += 1
    return stats

def send_summary(stats, title):
    if not stats:
        return

    total_stake = sum(s["stake"] for s in stats.values())
    total_profit = sum(s["profit"] for s in stats.values())
    total_roi = (total_profit / total_stake * 100) if total_stake else 0

    msg = f"{title}\n━━━━━━━━━━━━━━━━━━\n"
    msg += f"💰 Zysk/strata: {round(total_profit,2)} PLN | ROI {round(total_roi,2)}%\n"
    msg += "━━━━━━━━━━━━━━━━━━\n"

    for lg in LEAGUES:
        s = stats.get(lg, {"stake":0,"profit":0,"cnt":0, "pending":0})
        info = LEAGUE_INFO.get(lg, {"name": lg, "flag": "🎯"})

        if s.get("cnt",0) == 0 and s.get("pending",0) > 0:
            status_emoji = "⏳"
            profit_display = f"{s['pending']} zakładów pending"
            stake_display = f"| Stake: {round(s.get('stake',0),2)} PLN"
            roi_display = ""
        elif s.get("cnt",0) == 0:
            status_emoji = "⚪"
            profit_display = "Brak zakładów"
            stake_display = ""
            roi_display = ""
        else:
            status_emoji = "✅" if s["profit"] > 0 else "❌" if s["profit"] < 0 else "⏳"
            profit_display = f"{round(s['profit'],2)} PLN"
            roi_display = f"| ROI {round((s['profit']/s['stake']*100) if s['stake'] else 0,2)}%"
            stake_display = f"| Stake: {round(s['stake'],2)} PLN"

        msg += f"{info['flag']} {info['name']}: {status_emoji} {profit_display} {roi_display} ({s.get('cnt',0)}) {stake_display}\n"

    send_msg(msg, "results")

# ================= RESULTS =================
def check_results():
    coupons = load_json(COUPONS_FILE, [])
    bankroll = load_bankroll()

    for league in LEAGUES:
        for key in API_KEYS:
            try:
                r = requests.get(
                    f"https://api.the-odds-api.com/v4/sports/{league}/scores",
                    params={"apiKey": key, "daysFrom": 2},
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
                    else:
                        c["status"] = "lost"
                        c["win_val"] = 0
                break
            except:
                continue

    save_bankroll(bankroll)
    save_json(COUPONS_FILE, coupons)

# ================= RUN =================
def run():
    ensure_bankroll_file()
    check_results()

    coupons = load_json(COUPONS_FILE, [])
    meta = load_json(META_FILE, {})
    today = datetime.now(timezone.utc).date().isoformat()

    # Dzienny snapshot
    if meta.get("last_daily") != today:
        stats = league_stats(coupons, today, today)
        send_summary(stats, f"📊 PODSUMOWANIE DZIENNE • {today}")
        meta["last_daily"] = today

    # Tygodniowy snapshot
    year, week, _ = datetime.now(timezone.utc).isocalendar()
    wk = f"{year}-W{week}"
    if meta.get("last_weekly") != wk:
        start = (datetime.now(timezone.utc) - timedelta(days=7)).date().isoformat()
        stats = league_stats(coupons, start, today)
        send_summary(stats, f"🏆 PODSUMOWANIE TYGODNIOWE • {wk}")
        meta["last_weekly"] = wk

    save_json(META_FILE, meta)

if __name__ == "__main__":
    run()