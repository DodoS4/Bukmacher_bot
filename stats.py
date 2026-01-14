import json
from datetime import datetime, timedelta, timezone

COUPONS_FILE = "coupons.json"

def load_coupons():
    try:
        with open(COUPONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def filter_coupons(coupons, start, end):
    filtered = []
    for c in coupons:
        try:
            match_date = datetime.fromisoformat(c["date"])
            if start <= match_date <= end:
                filtered.append(c)
        except:
            continue
    return filtered

def generate_report(period="daily"):
    now = datetime.now(timezone.utc)

    if period == "daily":
        start = now - timedelta(days=1)
        label = "DZIENNY"
    elif period == "weekly":
        start = now - timedelta(days=7)
        label = "TYGODNIOWY"
    elif period == "monthly":
        start = now.replace(day=1)
        label = "MIESIĘCZNY"
    else:
        raise ValueError("Nieznany okres raportu")

    end = now
    coupons = load_coupons()
    filtered = filter_coupons(coupons, start, end)

    total_bets = len(filtered)
    won = sum(1 for c in filtered if c.get("status") == "WON")
    lost = sum(1 for c in filtered if c.get("status") == "LOST")
    pending = sum(1 for c in filtered if c.get("status") == "PENDING")
    profit = sum(c.get("profit", 0) for c in filtered)

    print(f"\n📊 RAPORT {label} – {start.strftime('%d.%m.%Y')} – {end.strftime('%d.%m.%Y')}")
    print("━━━━━━━━━━━━━━━━━━━━")
    print(f"🏆 Łącznie zakładów: {total_bets}")
    print(f"✅ Wygrane: {won}")
    print(f"❌ Przegrane: {lost}")
    print(f"⏳ Pending: {pending}")
    print(f"💰 Zysk/Strata: {'+' if profit>=0 else ''}{round(profit,2)} zł")
    print("━━━━━━━━━━━━━━━━━━━━")

    # Rozkład na ligi
    leagues = {}
    for c in filtered:
        league = c.get("league", "Inne")
        if league not in leagues:
            leagues[league] = {"bets":0, "won":0, "lost":0, "profit":0}
        leagues[league]["bets"] += 1
        if c.get("status") == "WON":
            leagues[league]["won"] += 1
        elif c.get("status") == "LOST":
            leagues[league]["lost"] += 1
        leagues[league]["profit"] += c.get("profit", 0)

    for league, stats in leagues.items():
        bar_len = 10
        if stats["bets"]:
            won_ratio = int(stats["won"]/stats["bets"]*bar_len)
        else:
            won_ratio = 0
        bar = "▓"*won_ratio + "░"*(bar_len-won_ratio)
        print(f"{league:<15} │ Bets: {stats['bets']:<3} │ ✅ {stats['won']:<3} │ ❌ {stats['lost']:<3} │ 💰 {'+' if stats['profit']>=0 else ''}{round(stats['profit'],2):<8} │ {bar}")

if __name__ == "__main__":
    generate_report("daily")
    generate_report("weekly")
    generate_report("monthly")