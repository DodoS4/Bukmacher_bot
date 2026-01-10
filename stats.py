import json, os
from datetime import datetime, timedelta, timezone

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

# ================= UTILS =================
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
        print("[DEBUG] Telegram skipped:\n", txt)
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

def load_bankroll():
    data = load_json(BANKROLL_FILE, {"bankroll": 10000.0})
    return data.get("bankroll", 10000.0)

# ================= REPORT GENERATOR =================
def generate_report(period_days=1, title="DAILY REPORT"):
    coupons = load_json(COUPONS_FILE, [])
    bankroll = load_bankroll()
    now = datetime.now(timezone.utc)
    start_period = now - timedelta(days=period_days)

    # Filtrowanie kuponów według okresu
    period_coupons = []
    for c in coupons:
        dt_str = c.get("date_time")
        if not dt_str:  # brak daty
            continue
        # Obsługa ISO z Z
        try:
            dt = datetime.fromisoformat(dt_str.replace("Z","+00:00"))
        except:
            continue
        if dt >= start_period:
            period_coupons.append(c)

    # Raport per liga
    league_stats = {}
    for c in period_coupons:
        league = c.get("league", "unknown")
        if league not in league_stats:
            league_stats[league] = {"won":0,"lost":0,"total":0,"profit":0.0}
        status = c.get("status","pending")
        stake = c.get("stake",0)
        odds = c.get("odds",0)
        league_stats[league]["total"] +=1
        if status=="won":
            league_stats[league]["won"]+=1
            league_stats[league]["profit"]+= stake*(odds-1)
        elif status=="lost":
            league_stats[league]["lost"]+=1
            league_stats[league]["profit"]-= stake

    msg = f"📊 <b>{title} • {now.date()}</b>\n💰 Bankroll: {bankroll:.2f} PLN\n\n"

    # Tworzenie raportu per ligę z paskiem zysku/straty
    for league, data in league_stats.items():
        total = data["total"]
        won = data["won"]
        lost = data["lost"]
        profit = data["profit"]
        hit_rate = int((won/total)*100) if total>0 else 0
        bar_length = 8
        filled = int(bar_length * (hit_rate/100))
        empty = bar_length - filled
        trend = "🔥" if profit>0 else "❌"
        league_name = LEAGUE_FLAGS.get(league, league.upper())
        msg += f"{trend} {league_name} | Typy: {total} | Wygrane: {won} | Przegrane: {lost} | Hit rate: {hit_rate}%\n"
        msg += f"{'█'*filled}{'░'*empty} | Zysk/Strata: {profit:.2f} PLN\n\n"

    # Najważniejsze mecze (top 5 po stawce)
    top_coupons = sorted(period_coupons, key=lambda x: x.get("stake",0), reverse=True)[:5]
    if top_coupons:
        msg += "🏟️ Najważniejsze mecze:\n"
        for c in top_coupons:
            dt_str = c.get("date_time","")
            try:
                dt = datetime.fromisoformat(dt_str.replace("Z","+00:00"))
                dt_display = dt.strftime("%Y-%m-%d %H:%M UTC")
            except:
                dt_display = dt_str
            status_icon = "✅" if c.get("status")=="won" else "❌" if c.get("status")=="lost" else "⌛"
            msg += f" • {c.get('home')} vs {c.get('away')} | Typ: {c.get('pick')} | Stawka: {c.get('stake')} PLN | {dt_display} | {status_icon}\n"

    print(msg)
    send_msg(msg)

# ================= DAILY / WEEKLY / MONTHLY =================
def generate_daily_report():
    generate_report(period_days=1, title="DAILY REPORT")

def generate_weekly_report():
    generate_report(period_days=7, title="WEEKLY REPORT")

def generate_monthly_report():
    generate_report(period_days=30, title="MONTHLY REPORT")

# ================= MAIN =================
if __name__=="__main__":
    import sys
    if "--daily" in sys.argv:
        generate_daily_report()
    elif "--weekly" in sys.argv:
        generate_weekly_report()
    elif "--monthly" in sys.argv:
        generate_monthly_report()
    else:
        generate_daily_report()