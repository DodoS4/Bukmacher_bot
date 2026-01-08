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
    os.getenv("ODDS_KEY_3"),
    os.getenv("ODDS_KEY_4"),
    os.getenv("ODDS_KEY_5")
] if k]

COUPONS_FILE = "coupons.json"
BANKROLL_FILE = "bankroll.json"
META_FILE = "meta.json"
START_BANKROLL = 100.0
MAX_HOURS_AHEAD = 72  # okno 72h

# ================= LEAGUES =================
LEAGUES = [
    "icehockey_nhl", "icehockey_khl",
    "basketball_nba", "basketball_euroleague",
    "soccer_epl", "soccer_england_championship", "soccer_poland_ekstraklasa",
    "soccer_germany_bundesliga", "soccer_uefa_champs_league",
    "soccer_italy_serie_a", "soccer_spain_la_liga", "soccer_italy_serie_b",
    "soccer_france_ligue_1"
]

LEAGUE_INFO = {
    "icehockey_nhl": {"name": "NHL", "flag": "🏒"},
    "icehockey_khl": {"name": "KHL", "flag": "🥅"},
    "basketball_nba": {"name": "NBA", "flag": "🏀"},
    "basketball_euroleague": {"name": "Euroliga", "flag": "🏀"},
    "soccer_epl": {"name": "Premier League", "flag": "🏴"},
    "soccer_england_championship": {"name": "Championship", "flag": "🏴"},
    "soccer_poland_ekstraklasa": {"name": "Ekstraklasa", "flag": "🇵🇱"},
    "soccer_germany_bundesliga": {"name": "Bundesliga", "flag": "🇩🇪"},
    "soccer_uefa_champs_league": {"name": "Champions League", "flag": "🏆"},
    "soccer_italy_serie_a": {"name": "Serie A", "flag": "🇮🇹"},
    "soccer_spain_la_liga": {"name": "La Liga", "flag": "🇪🇸"},
    "soccer_italy_serie_b": {"name": "Serie B", "flag": "🇮🇹"},
    "soccer_france_ligue_1": {"name": "Ligue 1", "flag": "🇫🇷"}
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

# ================= TELEGRAM =================
def send_msg(text, target="types"):
    chat_id = T_CHAT_RESULTS if target == "results" else T_CHAT
    if not T_TOKEN or not chat_id:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True},
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

# ================= RUN =================
def run_reports():
    coupons = load_json(COUPONS_FILE, [])
    meta = load_json(META_FILE, {})
    today = datetime.now(timezone.utc).date().isoformat()

    # Dzienny
    if meta.get("last_daily") != today:
        stats = league_stats(coupons, today, today)
        send_summary(stats, f"📊 PODSUMOWANIE DZIENNE • {today}")
        meta["last_daily"] = today

    # Tygodniowy
    year, week, _ = datetime.now(timezone.utc).isocalendar()
    wk = f"{year}-W{week}"
    if meta.get("last_weekly") != wk:
        start = (datetime.now(timezone.utc) - timedelta(days=7)).date().isoformat()
        stats = league_stats(coupons, start, today)
        send_summary(stats, f"🏆 PODSUMOWANIE TYGODNIOWE • {wk}")
        meta["last_weekly"] = wk

    # Miesięczny
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    if meta.get("last_monthly") != month:
        start = (datetime.now(timezone.utc).replace(day=1)).date().isoformat()
        stats = league_stats(coupons, start, today)
        send_summary(stats, f"📅 PODSUMOWANIE MIESIĘCZNE • {month}")
        meta["last_monthly"] = month

    save_json(META_FILE, meta)

if __name__ == "__main__":
    ensure_bankroll_file()
    run_reports()