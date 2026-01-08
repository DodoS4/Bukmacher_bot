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

MAX_HOURS_AHEAD = 24
VALUE_THRESHOLD = 0.035

MIN_ODDS_SOCCER = 2.50
MIN_ODDS_NHL = 2.30

# ================= LIGI =================
LEAGUES = [
    "icehockey_nhl",
    "basketball_nba",
    "soccer_epl",
    "soccer_germany_bundesliga",
    "soccer_uefa_champs_league"
]

LEAGUE_INFO = {
    "icehockey_nhl": {"name": "NHL", "flag": "🏒"},
    "basketball_nba": {"name": "NBA", "flag": "🏀"},
    "soccer_epl": {"name": "Premier League", "flag": "🏴"},
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

# ================= OFFERS / VALUE BET =================
def scan_offers():
    coupons = load_json(COUPONS_FILE, [])
    bankroll = load_bankroll()

    for league in LEAGUES:
        for key in API_KEYS:
            try:
                r = requests.get(
                    f"https://api.the-odds-api.com/v4/sports/{league}/odds/",
                    params={
                        "apiKey": key,
                        "regions": "us",
                        "markets": "h2h",
                        "bookmakers": "pinnacle"
                    },
                    timeout=10
                )
                if r.status_code != 200:
                    print(f"❌ {league}: błąd API ({r.status_code})")
                    continue

                matches = r.json()
                for m in matches:
                    start_time = parser.isoparse(m["commence_time"])
                    if start_time > datetime.now(timezone.utc) + timedelta(hours=MAX_HOURS_AHEAD):
                        continue

                    home = m["home_team"]
                    away = m["away_team"]

                    for b in m.get("bookmakers", []):
                        if b["key"] != "pinnacle":
                            continue
                        for market in b.get("markets", []):
                            for outcome in market.get("outcomes", []):
                                odds = outcome["price"]
                                picked = outcome["name"]

                                if league.startswith("soccer") and odds < MIN_ODDS_SOCCER:
                                    continue
                                if league.startswith("icehockey") and odds < MIN_ODDS_NHL:
                                    continue

                                edge = (odds * 0.5) - 1
                                if edge < VALUE_THRESHOLD:
                                    continue

                                stake = calc_kelly_stake(bankroll, odds, edge)
                                if stake < 3:
                                    continue

                                coupon = {
                                    "league": league,
                                    "home": home,
                                    "away": away,
                                    "picked": picked,
                                    "odds": odds,
                                    "stake": stake,
                                    "status": "pending",
                                    "sent_date": datetime.now(timezone.utc).isoformat()
                                }
                                coupons.append(coupon)
                break
            except Exception as e:
                print(f"❌ Błąd przy {league}: {e}")

    save_json(COUPONS_FILE, coupons)
    return coupons

# ================= STATS =================
def league_stats_visual(coupons, start, end):
    stats = {lg: {"stake": 0, "profit": 0, "cnt": 0, "pending": 0} for lg in LEAGUES}

    for c in coupons:
        sent_date = c.get("sent_date", "")
        if start <= sent_date[:10] <= end:
            lg = c["league"]
            if c["status"] == "pending":
                stats[lg]["pending"] += 1
            else:
                stats[lg]["stake"] += c["stake"]
                stats[lg]["profit"] += c["win_val"] if c["status"] == "won" else -c["stake"]
                stats[lg]["cnt"] += 1
    return stats

def send_summary_snapshot(coupons, start, end, title):
    stats = league_stats_visual(coupons, start, end)
    
    total_stake = sum(s["stake"] for s in stats.values())
    total_profit = sum(s["profit"] for s in stats.values())
    total_roi = (total_profit / total_stake * 100) if total_stake else 0

    msg = f"{title}\n━━━━━━━━━━━━━━━━━━\n"
    msg += f"💰 <b>Całkowity zysk:</b> {round(total_profit,2)} PLN | ROI {round(total_roi,2)}%\n━━━━━━━━━━━━━━━━━━\n"

    for lg in LEAGUES:
        s = stats.get(lg, {"stake":0, "profit":0, "cnt":0, "pending":0})
        roi = (s["profit"] / s["stake"] * 100) if s["stake"] else 0
        info = LEAGUE_INFO.get(lg, {"name": lg, "flag": "🎯"})

        if s["cnt"] == 0 and s["pending"] == 0:
            status_emoji = "⚪"
            status_text = "Brak zakładów"
        elif s["cnt"] == 0 and s["pending"] > 0:
            status_emoji = "⏳"
            status_text = f"{s['pending']} zakładów pending"
        elif s["profit"] >= 0:
            status_emoji = "✅"
            status_text = f"{round(s['profit'],2)} PLN | ROI {round(roi,2)}% ({s['cnt']})"
        else:
            status_emoji = "❌"
            status_text = f"{round(s['profit'],2)} PLN | ROI {round(roi,2)}% ({s['cnt']})"

        msg += f"{info['flag']} {info['name']}: {status_emoji} {status_text}\n"

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

    # 1️⃣ Pobranie ofert i value-betów
    coupons = scan_offers()

    # 2️⃣ Sprawdzenie wyników
    check_results()

    # 3️⃣ Raporty dzienne i tygodniowe
    meta = load_json(META_FILE, {})
    today = datetime.now(timezone.utc).date().isoformat()

    if meta.get("last_daily") != today:
        send_summary_snapshot(coupons, today, today, f"📊 <b>PODSUMOWANIE DZIENNE • {today}</b>")
        meta["last_daily"] = today

    year, week, _ = datetime.now(timezone.utc).isocalendar()
    wk = f"{year}-W{week}"
    if meta.get("last_weekly") != wk:
        start = (datetime.now(timezone.utc) - timedelta(days=7)).date().isoformat()
        send_summary_snapshot(coupons, start, today, f"🏆 <b>PODSUMOWANIE TYGODNIOWE • {wk}</b>")
        meta["last_weekly"] = wk

    save_json(META_FILE, meta)

if __name__ == "__main__":
    run()