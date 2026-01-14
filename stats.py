import json
import os
from datetime import datetime, timedelta, timezone

COUPONS_FILE = "coupons.json"

T_TOKEN = os.getenv("T_TOKEN")
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS")


# ================= TELEGRAM =================
def send_msg(txt):
    if not T_TOKEN or not T_CHAT_RESULTS:
        return
    try:
        import requests
        requests.post(
            f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
            json={"chat_id": T_CHAT_RESULTS, "text": txt, "parse_mode": "HTML"}
        )
    except Exception as e:
        print(f"[ERROR] Telegram: {e}")


# ================= LOAD COUPONS =================
def load_coupons():
    if not os.path.exists(COUPONS_FILE):
        return []
    try:
        with open(COUPONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERROR] load_coupons: {e}")
        return []


# ================= FILTER BY DATE =================
def filter_coupons(coupons, start):
    filtered = []
    for c in coupons:
        try:
            # Zamiana formatu 'Z' na '+00:00' dla fromisoformat
            dt_str = c["date"].replace("Z", "+00:00")
            dt = datetime.fromisoformat(dt_str)
            if dt >= start:
                filtered.append(c)
        except Exception:
            continue
    return filtered


# ================= GENERATE REPORT =================
def generate_report(period="daily"):
    coupons = load_coupons()
    now = datetime.now(timezone.utc)

    if period == "daily":
        start = now - timedelta(days=1)
        title = f"📊 RAPORT DZIENNY – {start.date()} – {now.date()}"
    elif period == "weekly":
        start = now - timedelta(days=7)
        title = f"📊 RAPORT TYGODNIOWY – {start.date()} – {now.date()}"
    elif period == "monthly":
        start = now.replace(day=1)
        title = f"📊 RAPORT MIESIĘCZNY – {start.date()} – {now.date()}"
    else:
        start = now - timedelta(days=1)
        title = f"📊 RAPORT – {now.date()}"

    filtered = filter_coupons(coupons, start)

    total = len(filtered)
    won = sum(1 for c in filtered if c.get("status") == "WON")
    lost = sum(1 for c in filtered if c.get("status") == "LOST")
    pending = sum(1 for c in filtered if c.get("status") == "PENDING")
    profit = sum(c.get("profit", 0) for c in filtered)

    # ====== Podział na ligi ======
    leagues = {}
    for c in filtered:
        league = c.get("league_name") or c.get("league_key") or "Unknown"
        if league not in leagues:
            leagues[league] = []
        leagues[league].append(c)

    # ====== Tworzenie tekstu ======
    lines = [title, "━━━━━━━━━━━━━━━━━━━━",
             f"🏆 Łącznie zakładów: {total}",
             f"✅ Wygrane: {won}",
             f"❌ Przegrane: {lost}",
             f"⏳ Pending: {pending}",
             f"💰 Zysk/Strata: {profit:.2f} zł",
             "━━━━━━━━━━━━━━━━━━━━",
             "📊 Rozkład na ligi:"]
    
    for league, bets in leagues.items():
        b_total = len(bets)
        b_won = sum(1 for c in bets if c.get("status") == "WON")
        b_lost = sum(1 for c in bets if c.get("status") == "LOST")
        b_pending = sum(1 for c in bets if c.get("status") == "PENDING")
        b_profit = sum(c.get("profit", 0) for c in bets)
        # wizualny pasek
        win_ratio = int((b_won / b_total) * 10) if b_total else 0
        bar = "▓" * win_ratio + "░" * (10 - win_ratio)
        lines.append(f"{league:<15} │ Bets: {b_total} │ ✅ {b_won} │ ❌ {b_lost} │ ⏳ {b_pending} │ 💰 {b_profit:.2f} zł │ {bar}")

    report = "\n".join(lines)
    print(report)
    send_msg(report)


# ================= MAIN =================
if __name__ == "__main__":
    generate_report("daily")
    generate_report("weekly")
    generate_report("monthly")