import json
from datetime import datetime, timedelta
from dateutil import parser
import os

COUPONS_FILE = "coupons.json"

def load_coupons():
    if not os.path.exists(COUPONS_FILE): 
        return []
    with open(COUPONS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def calculate_profit(c):
    return c.get("profit") if "profit" in c else 0

def generate_report(period="daily"):
    coupons = load_coupons()
    now = datetime.utcnow()

    if period == "daily":
        start = now - timedelta(days=1)
        title = "📊 RAPORT DZIENNY"
    elif period == "weekly":
        start = now - timedelta(days=7)
        title = "📊 RAPORT TYGODNIOWY"
    elif period == "monthly":
        start = now.replace(day=1)
        title = f"📊 RAPORT MIESIĘCZNY – {start.strftime('%d.%m')} – {now.strftime('%d.%m.%Y')}"
    else:
        start = datetime.min
        title = "📊 RAPORT"

    # Filtrowanie wg daty
    filtered = [c for c in coupons if parser.isoparse(c["date"]) >= start]

    total = len(filtered)
    won = sum(1 for c in filtered if c.get("status") == "WON")
    lost = sum(1 for c in filtered if c.get("status") == "LOST")
    pending = sum(1 for c in filtered if c.get("status") == "PENDING")
    total_profit = sum(calculate_profit(c) for c in filtered)

    # Grupowanie po ligach
    leagues = {}
    for c in filtered:
        league = c.get("league_name") or c.get("league") or c.get("league_key") or "Unknown"
        if league not in leagues:
            leagues[league] = []
        leagues[league].append(c)

    print(f"{title}")
    print("━━━━━━━━━━━━━━━━━━━━")
    print(f"🏆 Łącznie zakładów: {total}")
    print(f"✅ Wygrane: {won}")
    print(f"❌ Przegrane: {lost}")
    print(f"⏳ Pending: {pending}")
    print(f"💰 Zysk/Strata: {total_profit:+,.2f} zł")
    print("━━━━━━━━━━━━━━━━━━━━")
    print("📊 Rozkład na ligi:")

    for league, bets in leagues.items():
        l_total = len(bets)
        l_won = sum(1 for b in bets if b.get("status") == "WON")
        l_lost = sum(1 for b in bets if b.get("status") == "LOST")
        l_profit = sum(calculate_profit(b) for b in bets)

        # Pasek graficzny udziału wygranych
        ratio = int((l_won / l_total) * 10) if l_total else 0
        bar = "▓" * ratio + "░" * (10 - ratio)

        print(f"{league:<16} │ Bets: {l_total} │ ✅ {l_won} │ ❌ {l_lost} │ 💰 {l_profit:+,.2f} zł │ {bar}")

if __name__ == "__main__":
    # Generuj wszystkie trzy raporty
    generate_report("daily")
    generate_report("weekly")
    generate_report("monthly")