import json, os
from datetime import datetime, timedelta, timezone

T_TOKEN = os.getenv("T_TOKEN")
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS")
COUPONS_FILE = "coupons.json"

def send_msg(txt):
    if not T_TOKEN or not T_CHAT_RESULTS: return
    import requests
    try:
        requests.post(f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
                      json={"chat_id": T_CHAT_RESULTS, "text": txt, "parse_mode": "HTML"})
    except:
        pass

def load_coupons():
    if not os.path.exists(COUPONS_FILE): return []
    try:
        with open(COUPONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def generate_report(period="daily"):
    coupons = load_coupons()
    now = datetime.now(timezone.utc)

    if period == "daily":
        start = now - timedelta(days=1)
    elif period == "weekly":
        start = now - timedelta(days=7)
    elif period == "monthly":
        start = now.replace(day=1)
    else:
        start = datetime.min.replace(tzinfo=timezone.utc)

    filtered = [c for c in coupons if datetime.fromisoformat(c["date"]) >= start]

    total = len(filtered)
    won = sum(1 for c in filtered if c.get("status") == "WON")
    lost = sum(1 for c in filtered if c.get("status") == "LOST")
    pending = sum(1 for c in filtered if c.get("status") == "PENDING")
    profit = round(sum(c.get("profit",0) for c in filtered),2)

    # raport główny
    txt = (f"📊 RAPORT {period.upper()} – {start.strftime('%d.%m')} – {now.strftime('%d.%m.%Y')}\n"
           f"━━━━━━━━━━━━━━━━━━━━\n"
           f"🏆 Łącznie zakładów: {total}\n"
           f"✅ Wygrane: {won}\n"
           f"❌ Przegrane: {lost}\n"
           f"⏳ Pending: {pending}\n"
           f"💰 Zysk/Strata: {profit} zł\n"
           f"━━━━━━━━━━━━━━━━━━━━\n"
           f"📊 Rozkład na ligi:")

    # liga stats
    leagues = {}
    for c in filtered:
        lk = c["league"]
        if lk not in leagues:
            leagues[lk] = {"bets":0,"won":0,"lost":0,"profit":0.0}
        leagues[lk]["bets"] +=1
        leagues[lk]["won"] += 1 if c.get("status")=="WON" else 0
        leagues[lk]["lost"] += 1 if c.get("status")=="LOST" else 0
        leagues[lk]["profit"] += c.get("profit",0)

    for lk, stats in leagues.items():
        total_bars = 10
        won_ratio = stats["won"]/stats["bets"] if stats["bets"] else 0
        bars = int(total_bars * won_ratio)
        txt += f"\n{lk:20} │ Bets: {stats['bets']} │ ✅ {stats['won']} │ ❌ {stats['lost']} │ 💰 {round(stats['profit'],2)} zł │ {'▓'*bars}{'░'*(total_bars-bars)}"

    send_msg(txt)
    print(txt)

if __name__ == "__main__":
    generate_report("daily")