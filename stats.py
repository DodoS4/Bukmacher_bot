import json, os
from datetime import datetime, timedelta

COUPONS_FILE = "coupons.json"

def load_coupons():
    if not os.path.exists(COUPONS_FILE): return []
    try:
        with open(COUPONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except: return []

def generate_report(period="daily"):
    coupons = load_coupons()
    now = datetime.utcnow()

    if period=="daily":
        start = now - timedelta(days=1)
        title = f"📊 RAPORT DZIENNY – {start.strftime('%d.%m.%Y')}"
    elif period=="weekly":
        start = now - timedelta(days=7)
        title = f"📊 RAPORT TYGODNIOWY – {start.strftime('%d.%m.%Y')} – {now.strftime('%d.%m.%Y')}"
    elif period=="monthly":
        start = now.replace(day=1)
        title = f"📊 RAPORT MIESIĘCZNY – {start.strftime('%d.%m')} – {now.strftime('%d.%m.%Y')}"
    else:
        start = datetime.min
        title = "📊 RAPORT"

    filtered = [c for c in coupons if datetime.fromisoformat(c["date"]) >= start]

    total = len(filtered)
    won = sum(1 for c in filtered if c.get("status")=="WON")
    lost = sum(1 for c in filtered if c.get("status")=="LOST")
    pending = sum(1 for c in filtered if c.get("status")=="PENDING")
    profit = sum(c.get("profit",0) for c in filtered)

    # Podział na ligi
    leagues = {}
    for c in filtered:
        league = c.get("league_name","Inne")
        if league not in leagues:
            leagues[league] = {"bets":0,"won":0,"lost":0,"profit":0}
        leagues[league]["bets"] +=1
        if c.get("status")=="WON": leagues[league]["won"]+=1
        if c.get("status")=="LOST": leagues[league]["lost"]+=1
        leagues[league]["profit"] += c.get("profit",0)

    # Raport
    lines = [title, "━━━━━━━━━━━━━━━━━━━━",
             f"🏆 Łącznie zakładów: {total}",
             f"✅ Wygrane: {won}",
             f"❌ Przegrane: {lost}",
             f"⏳ Pending: {pending}",
             f"💰 Zysk/Strata: {'+' if profit>=0 else ''}{round(profit,2)} zł",
             "━━━━━━━━━━━━━━━━━━━━",
             "📊 Rozkład na ligi:"]
    
    for league,data in leagues.items():
        total_bets = data["bets"]
        w = data["won"]
        l = data["lost"]
        pft = data["profit"]
        # pasek procentowy
        total_wl = w+l if (w+l)>0 else 1
        filled = int(w/total_wl*8)
        empty = 8-filled
        bar = "▓"*filled + "░"*empty
        lines.append(f"{league:<15} │ Bets: {total_bets} │ ✅ {w} │ ❌ {l} │ 💰 {'+' if pft>=0 else ''}{round(pft,2)} zł │ {bar}")

    report = "\n".join(lines)
    print(report)
    return report

if __name__=="__main__":
    # wygenerowanie wszystkich raportów
    generate_report("daily")
    generate_report("weekly")
    generate_report("monthly")