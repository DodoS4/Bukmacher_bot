import json
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone

# ================= KONFIG =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS")
COUPONS_FILE = "coupons.json"

# ================= FUNKCJE =================
def load_coupons():
    """Ładuje zapisane kupony z pliku JSON"""
    if os.path.exists(COUPONS_FILE):
        with open(COUPONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def send_msg(txt):
    """Wysyła wiadomość na Telegram lub drukuje debug"""
    if not T_TOKEN or not T_CHAT_RESULTS:
        print("[DEBUG] Telegram skipped:\n", txt)
        return
    try:
        import requests
        requests.post(
            f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
            json={"chat_id": T_CHAT_RESULTS, "text": txt, "parse_mode": "HTML"},
            timeout=10
        )
    except Exception as e:
        print(f"[DEBUG] Telegram error: {e}")

def generate_report(period_days=1, title="DAILY REPORT"):
    """Generuje raport per ligę dla ostatnich period_days dni"""
    coupons = load_coupons()
    if not coupons:
        print("Brak typów w pliku.")
        return

    now = datetime.now(timezone.utc)
    start_period = now - timedelta(days=period_days)

    leagues = defaultdict(lambda: {"won":0,"lost":0,"stake":0,"profit":0,"total":0})

    for c in coupons:
        c_dt = datetime.fromisoformat(c.get("date_time").replace("Z","+00:00"))
        if c_dt < start_period:
            continue  # pomijamy starsze kupony

        league = c.get("league","unknown")
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

    report = f"📊 <b>{title} • {now.date()}</b>\n\n"
    for league, data in leagues.items():
        total = data["total"]
        if total == 0:
            continue
        won = data["won"]
        lost = data["lost"]
        profit = data["profit"]
        hit_rate = int((won/total)*100)
        # blok graficzny: 10 znaków
        blocks = int(hit_rate/10)
        bar = "█"*blocks + "░"*(10-blocks)
        emoji = "🔥" if profit>0 else "❌" if profit<0 else "➖"
        report += (
            f"{emoji} {league} | Typy: {total} | Wygrane: {won} | Przegrane: {lost} | Hit rate: {hit_rate}%\n"
            f"{bar} | Zysk/Strata: {profit:.2f} PLN\n\n"
        )

    print(report)
    send_msg(report)

# ================= RAPORTY =================
def daily_report():
    generate_report(period_days=1, title="DAILY REPORT")

def weekly_report():
    generate_report(period_days=7, title="WEEKLY REPORT")

def monthly_report():
    generate_report(period_days=30, title="MONTHLY REPORT")

# ================= MAIN =================
if __name__ == "__main__":
    import sys
    if "--daily" in sys.argv:
        daily_report()
    elif "--weekly" in sys.argv:
        weekly_report()
    elif "--monthly" in sys.argv:
        monthly_report()
    else:
        # domyślnie dzienny
        daily_report()