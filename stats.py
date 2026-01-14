import json
from datetime import datetime, timedelta, timezone
import os

COUPONS_FILE = "coupons.json"
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS")

def load_coupons():
    try:
        with open(COUPONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def generate_report(period="daily"):
    coupons = load_coupons()
    now = datetime.now(timezone.utc)
    
    if period == "daily":
        since = now - timedelta(days=1)
        title = "📊 RAPORT DZIENNY"
    elif period == "weekly":
        since = now - timedelta(days=7)
        title = "📊 RAPORT TYGODNIOWY"
    elif period == "monthly":
        since = now.replace(day=1)
        title = "📊 RAPORT MIESIĘCZNY"
    else:
        return

    data = [c for c in coupons if datetime.fromisoformat(c["date"].replace("Z", "+00:00")) >= since]
    total = len(data)
    won = len([c for c in data if c["status"] == "✅ Wygrany"])
    lost = len([c for c in data if c["status"] == "❌ Przegrany"])
    pending = len([c for c in data if c["status"] == "Pending"])
    profit = sum([c["odds"]-1 for c in data if c["status"] == "✅ Wygrany"]) * 100  # stawka 100zł

    print(title)
    print("━━━━━━━━━━━━━━━━━━━━")
    print(f"🏆 Łącznie zakładów: {total}")
    print(f"✅ Wygrane: {won}")
    print(f"❌ Przegrane: {lost}")
    print(f"⏳ Pending: {pending}")
    print(f"💰 Zysk/Strata: {profit:.2f} zł")
    print("━━━━━━━━━━━━━━━━━━━━")

    # ranking lig
    leagues = {}
    for c in data:
        if c["league"] not in leagues:
            leagues[c["league"]] = {"bets":0,"profit":0}
        leagues[c["league"]]["bets"] +=1
        if c["status"] == "✅ Wygrany":
            leagues[c["league"]]["profit"] += (c["odds"]-1)*100
        elif c["status"] == "❌ Przegrany":
            leagues[c["league"]]["profit"] -= 100

    print("📊 RANKING LIG – OSTATNIE 30 DNI")
    print("━━━━━━━━━━━━━━━━━━━━")
    print(f"{'Liga':<20} Bets   ROI     Profit")
    print("━━━━━━━━━━━━━━━━━━━━")
    for league, stats in leagues.items():
        roi = (stats["profit"]/ (stats["bets"]*100))*100 if stats["bets"]>0 else 0
        emoji = "✅" if roi>0 else "❌"
        print(f"{league:<20} {stats['bets']:<5} {roi:+.1f}%   {stats['profit']:+.0f} zł {emoji}")
    print("━━━━━━━━━━━━━━━━━━━━")

if __name__ == "__main__":
    generate_report("daily")
    generate_report("weekly")
    generate_report("monthly")