import json, os
from datetime import datetime, timedelta, timezone
from dateutil import parser
import requests

FILE = "coupons.json"

T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT_RESULTS")

def send(msg):
    if not T_TOKEN or not T_CHAT:
        return
    requests.post(
        f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
        json={"chat_id": T_CHAT, "text": msg},
        timeout=10
    )

def safe_date(d):
    try:
        return parser.isoparse(d).astimezone(timezone.utc)
    except:
        return None

def report(days, title):
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days)

    coupons = json.load(open(FILE, encoding="utf-8"))

    data = []
    for c in coupons:
        d = safe_date(c.get("date"))
        if not d:
            continue
        if d >= since:
            data.append(c)

    won = sum(1 for c in data if c.get("status") == "won")
    lost = sum(1 for c in data if c.get("status") == "lost")
    pending = sum(1 for c in data if c.get("status") == "pending")
    profit = round(sum(c.get("profit", 0) for c in data if c.get("status") in ("won", "lost")), 2)

    leagues = {}
    for c in data:
        lg = c.get("league_name") or c.get("league_key", "OTHER")
        leagues.setdefault(lg, {"bets": 0, "won": 0, "lost": 0, "profit": 0})
        leagues[lg]["bets"] += 1
        if c.get("status") == "won":
            leagues[lg]["won"] += 1
            leagues[lg]["profit"] += c.get("profit", 0)
        elif c.get("status") == "lost":
            leagues[lg]["lost"] += 1
            leagues[lg]["profit"] += c.get("profit", 0)

    msg = (
        f"📊 {title}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏆 Zakładów: {len(data)}\n"
        f"✅ Wygrane: {won}\n"
        f"❌ Przegrane: {lost}\n"
        f"⏳ Pending: {pending}\n"
        f"💰 Zysk/Strata: {profit:+,.2f} zł\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 Ligi:\n"
    )

    for lg, s in leagues.items():
        msg += (
            f"{lg} │ Bets: {s['bets']} │ "
            f"✅ {s['won']} │ ❌ {s['lost']} │ "
            f"💰 {s['profit']:+,.2f} zł\n"
        )

    send(msg)

# ================= RUN =================
report(1, "RAPORT DZIENNY")
report(7, "RAPORT TYGODNIOWY")
report(30, "RAPORT MIESIĘCZNY")