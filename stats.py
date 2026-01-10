import json, os
from datetime import datetime, timedelta, timezone
from collections import defaultdict

# ================= CONFIG =================
COUPONS_FILE = "coupons.json"
BANKROLL_FILE = "bankroll.json"
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS")

LEAGUE_FLAGS = {
    "basketball_nba": "🏀 NBA",
    "icehockey_nhl": "🏒 NHL",
    "soccer_epl": "⚽ EPL",
    "soccer_germany_bundesliga": "⚽ Bundesliga",
    "soccer_italy_serie_a": "⚽ Serie A"
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

def send_msg(txt):
    if not T_TOKEN or not T_CHAT_RESULTS:
        print(txt)
        return
    import requests
    try:
        requests.post(
            f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
            json={"chat_id": T_CHAT_RESULTS, "text": txt, "parse_mode": "HTML"},
            timeout=10
        )
    except Exception as e:
        print(f"[DEBUG] Telegram error: {e}")

# ================= BANKROLL =================
def load_bankroll():
    data = load_json(BANKROLL_FILE, {"bankroll": 10000})
    return data.get("bankroll", 10000)

# ================= REPORT =================
def generate_report(period_days=1, title="DAILY REPORT"):
    coupons = load_json(COUPONS_FILE, [])
    now = datetime.now(timezone.utc)
    start_time = now - timedelta(days=period_days)

    # Grupowanie po ligach
    report_data = defaultdict(lambda: {"won":0,"lost":0,"profit":0.0,"total":0})
    matches = []

    for c in coupons:
        c_dt_str = c.get("date_time", None)
        c_dt = None
        try:
            if c_dt_str:
                c_dt = datetime.fromisoformat(c_dt_str.replace("Z","+00:00"))
        except:
            pass

        # Filtr wg okresu
        if c_dt and c_dt < start_time:
            continue

        league = c.get("league","unknown")
        report_data[league]["total"] += 1
        stake = c.get("stake",0)
        odds = c.get("odds",0)

        if c.get("status")=="won":
            report_data[league]["won"] += 1
            report_data[league]["profit"] += stake*(odds-1)
        elif c.get("status")=="lost":
            report_data[league]["lost"] += 1
            report_data[league]["profit"] -= stake

        matches.append(c)

    bankroll = load_bankroll()
    msg = f"📊 {title} • {now.date()}\n💰 Bankroll: {bankroll:.2f} PLN\n\n"

    # Raport per liga
    for league, data in report_data.items():
        won = data["won"]
        lost = data["lost"]
        total = data["total"]
        profit = data["profit"]
        hit_rate = int((won/total)*100) if total>0 else 0

        # pasek hit rate
        bar_len = 8
        filled = int(bar_len * hit_rate/100)
        bar = "█"*filled + "░"*(bar_len-filled)

        flag = LEAGUE_FLAGS.get(league, league.upper())
        emoji = "🔥" if profit>=0 else "❌"

        msg += f"{emoji} {flag} | Typy: {total} | Wygrane: {won} | Przegrane: {lost} | Hit rate: {hit_rate}%\n"
        msg += f"{bar} | Zysk/Strata: {profit:.2f} PLN\n\n"

    # Najważniejsze mecze
    if matches:
        msg += "🏟️ Najważniejsze mecze:\n"
        for m in matches[:5]:
            stake = m.get("stake",0)
            odds = m.get("odds",0)
            potential_win = stake*(odds)
            status = m.get("status","pending")
            status_icon = "✅" if status=="won" else "❌" if status=="lost" else "⌛"
            msg += f"\t• {m.get('home')} vs {m.get('away')} | Typ: {m.get('pick')} | Stawka: {stake:.2f} PLN | Potencjalna wygrana: {potential_win:.2f} PLN | {status_icon}\n"

    send_msg(msg)

# ================= MAIN =================
if __name__=="__main__":
    import sys
    arg = sys.argv[1] if len(sys.argv)>1 else "daily"
    if arg=="daily":
        generate_report(period_days=1, title="DAILY REPORT")
    elif arg=="weekly":
        generate_report(period_days=7, title="WEEKLY REPORT")
    elif arg=="monthly":
        generate_report(period_days=30, title="MONTHLY REPORT")