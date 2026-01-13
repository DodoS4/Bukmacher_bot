import json
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import requests

# ================= CONFIG =================
FILE = "coupons_notax.json"
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS")

# ================= HELPERS =================
def send_msg(txt):
    if not T_TOKEN or not T_CHAT_RESULTS:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
            json={
                "chat_id": T_CHAT_RESULTS,
                "text": txt,
                "parse_mode": "HTML"
            }
        )
    except:
        pass

def load():
    if not os.path.exists(FILE):
        return []
    with open(FILE, "r", encoding="utf-8") as f:
        return json.load(f)

# ================= STATS =================
def calc_stats(coupons):
    total = len(coupons)
    win = sum(1 for c in coupons if c["status"] == "WIN")
    lose = sum(1 for c in coupons if c["status"] == "LOSE")
    profit = sum(c.get("profit", 0) for c in coupons)

    return total, win, lose, round(profit, 2)

# ================= WEEKLY REPORT =================
def run_weekly_report():
    coupons = load()
    if not coupons:
        send_msg("📊 Brak danych do raportu")
        return

    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)

    weekly = []
    for c in coupons:
        try:
            d = datetime.fromisoformat(c["date"])
            if d >= week_ago:
                weekly.append(c)
        except:
            continue

    if not weekly:
        send_msg("📊 Brak zakładów z ostatnich 7 dni")
        return

    leagues = defaultdict(list)
    for c in weekly:
        league = (
            c.get("league_name")
            or c.get("league_key")
            or "UNKNOWN"
        )
        leagues[league].append(c)

    total, win, lose, profit = calc_stats(weekly)

    msg = (
        f"📊 <b>STATYSTYKI – OSTATNIE 7 DNI</b>\n\n"
        f"Łącznie zakładów: <b>{total}</b>\n"
        f"✅ Wygrane: <b>{win}</b>\n"
        f"❌ Przegrane: <b>{lose}</b>\n"
        f"💰 Zysk/Strata: <b>{profit} zł</b>\n\n"
        f"<b>Podział na ligi:</b>\n"
    )

    for lg, bets in leagues.items():
        t, w, l, p = calc_stats(bets)
        msg += f"• {lg}: {t} | ✅ {w} | ❌ {l} | 💰 {p} zł\n"

    send_msg(msg)

# ================= RUN =================
if __name__ == "__main__":
    run_weekly_report()