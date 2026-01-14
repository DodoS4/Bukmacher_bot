import json
import os
from datetime import datetime, timedelta

COUPONS_FILE = "coupons_notax.json"

DAYS = 7

def load():
    if not os.path.exists(COUPONS_FILE):
        return []
    with open(COUPONS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def in_last_days(c, days):
    ts = c.get("created_at") or c.get("time")
    if not ts:
        return True
    try:
        dt = datetime.fromisoformat(ts.replace("Z", ""))
        return dt >= datetime.utcnow() - timedelta(days=days)
    except:
        return True

def run():
    data = load()
    data = [c for c in data if in_last_days(c, DAYS)]

    total = len(data)
    won = lost = pending = 0
    profit = 0.0

    leagues = {}

    for c in data:
        league = c.get("league_name") or c.get("league_key", "UNKNOWN")
        leagues.setdefault(league, {
            "bets": 0,
            "won": 0,
            "lost": 0,
            "pending": 0,
            "profit": 0.0
        })

        leagues[league]["bets"] += 1

        status = c.get("status", "PENDING")

        if status == "WON":
            won += 1
            leagues[league]["won"] += 1
            profit += c.get("profit", 0)
            leagues[league]["profit"] += c.get("profit", 0)

        elif status == "LOST":
            lost += 1
            leagues[league]["lost"] += 1
            profit += c.get("profit", 0)
            leagues[league]["profit"] += c.get("profit", 0)

        else:
            pending += 1
            leagues[league]["pending"] += 1

    print("\n📊 STATYSTYKI – OSTATNIE 7 DNI\n")
    print(f"Łącznie zakładów: {total}")
    print(f"✅ Wygrane: {won}")
    print(f"❌ Przegrane: {lost}")
    print(f"⏳ Pending: {pending}")
    print(f"💰 Zysk/Strata: {round(profit,2)} zł\n")

    print("Podział na ligi:")
    for l, s in leagues.items():
        print(
            f"• {l}: {s['bets']} | "
            f"✅ {s['won']} | ❌ {s['lost']} | ⏳ {s['pending']} | "
            f"💰 {round(s['profit'],2)} zł"
        )

if __name__ == "__main__":
    run()