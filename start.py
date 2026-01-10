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

MAX_HOURS_AHEAD = 48
VALUE_THRESHOLD = 0.02
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

LEAGUE_FLAGS = {
    "basketball_nba": "🏀 NBA",
    "icehockey_nhl": "🏒 NHL",
    "soccer_epl": "⚽ EPL",
    "soccer_germany_bundesliga": "⚽ BUN",
    "soccer_italy_serie_a": "⚽ SER"
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

# ================= TELEGRAM =================
def send_msg(txt, target="types"):
    chat = T_CHAT_RESULTS if target == "results" else T_CHAT
    if not T_TOKEN or not chat:
        print(f"[DEBUG] Telegram skipped:\n{txt}")
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

# ================= REPORT GENERATOR =================
def generate_report(period_days=1, title="DAILY REPORT"):
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=period_days)
    coupons = load_json(COUPONS_FILE, [])
    
    filtered = []
    for c in coupons:
        dt_str = c.get("date_time")
        if not dt_str:
            continue
        c_dt = parser.isoparse(dt_str)
        if c_dt >= cutoff:
            filtered.append(c)
    
    bankroll = load_bankroll()
    msg = f"📊 {title} • {now.date()}\n💰 Bankroll: {bankroll:.2f} PLN\n\n"

    leagues = defaultdict(lambda: {"won":0,"lost":0,"profit":0.0,"total":0})
    for c in filtered:
        league = c.get("league","unknown")
        leagues[league]["total"] += 1
        stake = c.get("stake",0)
        odds = c.get("odds",0)
        status = c.get("status","pending")
        if status=="won":
            leagues[league]["won"] += 1
            leagues[league]["profit"] += stake*(odds-1)
        elif status=="lost":
            leagues[league]["lost"] += 1
            leagues[league]["profit"] -= stake

    for league, data in leagues.items():
        total, won, lost, profit = data["total"], data["won"], data["lost"], data["profit"]
        hit_rate = int((won/total)*100) if total>0 else 0
        bar_len = 7
        filled = int(bar_len * hit_rate / 100)
        empty = bar_len - filled
        emoji = "🔥" if profit>0 else "❌"
        league_name = LEAGUE_FLAGS.get(league, league.upper())
        msg += f"{emoji} {league_name} | Typy: {total} | Wygrane: {won} | Przegrane: {lost} | Hit rate: {hit_rate}%\n"
        msg += f"{'█'*filled}{'░'*empty} | Zysk/Strata: {profit:.2f} PLN\n\n"

    # Najważniejsze mecze dnia - top 5 po stawce
    filtered_sorted = sorted(filtered, key=lambda x: x.get("stake",0), reverse=True)
    top5 = filtered_sorted[:5]
    if top5:
        msg += "🏟️ Najważniejsze mecze dnia:\n"
        for c in top5:
            status_icon = "✅" if c.get("status")=="won" else "❌" if c.get("status")=="lost" else "⏳"
            msg += f"\t• {c.get('home')} vs {c.get('away')} | Typ: {c.get('pick')} | Stawka: {c.get('stake'):.2f} PLN | {status_icon}\n"

    print("[DEBUG] Report:\n", msg)
    send_msg(msg, target="results")

# ================= MAIN =================
if __name__ == "__main__":
    if "--report" in sys.argv:
        arg_index = sys.argv.index("--report") + 1
        period = sys.argv[arg_index] if len(sys.argv) > arg_index else "daily"
        if period=="daily":
            generate_report(period_days=1, title="DAILY REPORT")
        elif period=="weekly":
            generate_report(period_days=7, title="WEEKLY REPORT")
        elif period=="monthly":
            generate_report(period_days=30, title="MONTHLY REPORT")
        else:
            generate_report(period_days=1, title="DAILY REPORT")
    else:
        # Tu zostaw normalne uruchomienie bota z typami
        print("⚔️ Uruchamianie bota z typami... (tutaj Twój kod typów)")