import json
import os
from datetime import datetime, timedelta, timezone
from collections import defaultdict

# ================= KONFIG =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS")
COUPONS_FILE = "coupons.json"

# ================= UTILS =================
def load_coupons():
    if os.path.exists(COUPONS_FILE):
        with open(COUPONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def send_msg(txt):
    if not T_TOKEN or not T_CHAT_RESULTS:
        print("[DEBUG] Telegram skipped:\n", txt)
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
            json={"chat_id": T_CHAT_RESULTS, "text": txt, "parse_mode": "HTML"},
            timeout=10
        )
    except Exception as e:
        print(f"[DEBUG] Telegram error: {e}")

def parse_datetime(dt_str):
    """Zamienia ISO z 'Z' na +00:00 aby działało w Python 3.9"""
    if dt_str.endswith("Z"):
        dt_str = dt_str.replace("Z", "+00:00")
    return datetime.fromisoformat(dt_str)

# ================= RAPORT =================
def generate_report(period_days=1, title="RAPORT"):
    coupons = load_coupons()
    now = datetime.now(timezone.utc)
    period_start = now - timedelta(days=period_days)

    # Filtrujemy tylko kupony z okresu
    period_coupons = []
    for c in coupons:
        dt_str = c.get("date_time", "2100-01-01T00:00:00Z")
        c_dt = parse_datetime(dt_str)
        if c_dt >= period_start:
            period_coupons.append(c)

    # Raport per liga
    leagues = defaultdict(lambda: {"won":0,"lost":0,"stake":0,"profit":0,"total":0})
    for c in period_coupons:
        league = c.get("league","unknown").upper()
        status = c.get("status","pending")
        stake = c.get("stake",0)
        odds = c.get("odds",0)
        leagues[league]["total"] += 1
        leagues[league]["stake"] += stake
        if status == "won":
            leagues[league]["won"] += 1
            leagues[league]["profit"] += stake*(odds-1)
        elif status == "lost":
            leagues[league]["lost"] += 1
            leagues[league]["profit"] -= stake

    # Mapa flag
    FLAGS = {
        "BASKETBALL_NBA":"🏀 NBA",
        "ICEHOCKEY_NHL":"🏒 NHL",
        "SOCCER_EPL":"⚽ EPL",
        "SOCCER_GERMANY_BUNDESLIGA":"⚽ BUNDESLIGA",
        "SOCCER_ITALY_SERIE_A":"⚽ SERIE A"
    }

    msg = f"📊 {title} • {now.date()}\n"
    bankroll_total = sum(
        (c.get("stake",0)*(c.get("odds",0)-1) if c["status"]=="won" else -c.get("stake",0))
        for c in period_coupons
    )
    msg += f"💰 Bankroll: {bankroll_total:.2f} PLN\n\n"

    for league, data in leagues.items():
        total = data["total"]
        won = data["won"]
        lost = data["lost"]
        profit = data["profit"]
        hit_rate = int((won/total)*100) if total>0 else 0
        bars = "█" * int(hit_rate/10) + "░" * (10 - int(hit_rate/10))
        emoji = "🔥" if profit>0 else "❌"

        msg += f"{emoji} {FLAGS.get(league, league)} | Typy: {total} | Wygrane: {won} | Przegrane: {lost} | Hit rate: {hit_rate}%\n"
        msg += f"{bars} | Zysk/Strata: {profit:.2f} PLN\n\n"

    # Najważniejsze mecze dnia (max 5)
    period_coupons.sort(key=lambda x: parse_datetime(x.get("date_time","2100-01-01T00:00:00Z")))
    msg += "🏟️ Najważniejsze mecze dnia:\n"
    for c in period_coupons[:5]:
        dt_obj = parse_datetime(c.get("date_time","2100-01-01T00:00:00Z"))
        status_icon = "✅" if c["status"]=="won" else "❌" if c["status"]=="lost" else "⏳"
        msg += f"\t• {c.get('home','')} vs {c.get('away','')} | Typ: {c.get('pick','')} | Stawka: {c.get('stake',0):.2f} PLN | Data: {dt_obj.strftime('%Y-%m-%d %H:%M UTC')} | {status_icon}\n"

    print(msg)
    send_msg(msg)

def generate_daily_report():
    generate_report(period_days=1, title="DAILY REPORT")

def generate_weekly_report():
    generate_report(period_days=7, title="WEEKLY REPORT")

def generate_monthly_report():
    generate_report(period_days=30, title="MONTHLY REPORT")

# ================= MAIN =================
if __name__ == "__main__":
    import sys
    if "--report" in sys.argv:
        arg_idx = sys.argv.index("--report")
        if len(sys.argv) > arg_idx+1:
            period = sys.argv[arg_idx+1].lower()
            if period=="daily":
                generate_daily_report()
            elif period=="weekly":
                generate_weekly_report()
            elif period=="monthly":
                generate_monthly_report()
            else:
                generate_daily_report()
        else:
            generate_daily_report()
    else:
        print("Brak raportu, uruchom z --report daily|weekly|monthly")