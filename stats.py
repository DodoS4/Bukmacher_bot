import json, os, requests
from datetime import datetime, timedelta, timezone
from collections import defaultdict

# ================= KONFIG =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS")
COUPONS_FILE = "coupons.json"

# ================= FUNKCJE POMOCNICZE =================
def load_coupons():
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
        requests.post(
            f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
            json={"chat_id": T_CHAT_RESULTS, "text": txt, "parse_mode": "HTML"},
            timeout=10
        )
    except Exception as e:
        print(f"[DEBUG] Telegram error: {e}")

def calc_hit_bar(hit_rate):
    """Generuje pasek trafień dla wizualizacji procentowej"""
    total_blocks = 10
    filled = int(round(hit_rate / 10))
    empty = total_blocks - filled
    return "█"*filled + "░"*empty

# ================= RAPORT =================
def generate_report(period="daily"):
    coupons = load_coupons()
    if not coupons:
        send_msg(f"📊 Brak typów do raportu ({period})")
        return

    now = datetime.now(timezone.utc)
    if period == "daily":
        start_time = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
        end_time = start_time + timedelta(days=1)
        title = f"📊 RAPORT DZIENNY • {now.date()}"
    elif period == "weekly":
        start_time = now - timedelta(days=7)
        end_time = now + timedelta(seconds=1)
        title = f"📊 RAPORT TYGODNIOWY • {now.date()}"
    elif period == "monthly":
        start_time = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_time = now + timedelta(seconds=1)
        title = f"📊 RAPORT MIESIĘCZNY • {now.date()}"
    else:
        start_time = datetime.min.replace(tzinfo=timezone.utc)
        end_time = datetime.max.replace(tzinfo=timezone.utc)
        title = f"📊 RAPORT • {now.date()}"

    # Filtrujemy kupony wg okresu
    filtered = []
    for c in coupons:
        dt_str = c.get("date_time", None)
        if not dt_str:
            continue
        try:
            dt = datetime.fromisoformat(dt_str)
        except:
            continue
        if start_time <= dt <= end_time:
            filtered.append(c)

    # Grupowanie po lidze
    report = defaultdict(lambda: {"won":0, "lost":0, "profit":0.0, "total":0})
    for c in filtered:
        league = c.get("league", "unknown")
        stake = c.get("stake", 0)
        odds = c.get("odds", 0)
        status = c.get("status", "pending")

        report[league]["total"] += 1
        if status == "won":
            report[league]["won"] += 1
            report[league]["profit"] += stake*(odds-1)
        elif status == "lost":
            report[league]["lost"] += 1
            report[league]["profit"] -= stake

    # Tworzenie wiadomości
    msg = f"{title}\n\n"
    for league, data in report.items():
        total = data["total"]
        won = data["won"]
        lost = data["lost"]
        profit = data["profit"]
        hit_rate = int((won/total)*100) if total>0 else 0
        bar = calc_hit_bar(hit_rate)
        emoji = "🔥" if profit>0 else "❌"

        msg += (f"{emoji} {league} | Typy: {total} | Wygrane: {won} | Przegrane: {lost} | Hit rate: {hit_rate}%\n"
                f"{bar} | Zysk/Strata: {profit:.2f} PLN\n\n")

    send_msg(msg)

# ================= MAIN =================
if __name__ == "__main__":
    import sys
    if "--daily" in sys.argv:
        generate_report("daily")
    elif "--weekly" in sys.argv:
        generate_report("weekly")
    elif "--monthly" in sys.argv:
        generate_report("monthly")
    else:
        generate_report("daily")