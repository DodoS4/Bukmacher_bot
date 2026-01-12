import json, os
from datetime import datetime, timedelta, timezone
from collections import defaultdict
import requests

COUPONS_FILE = "coupons_notax.json"
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS")

def send_msg(txt):
    if not T_TOKEN or not T_CHAT_RESULTS:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
            json={"chat_id": T_CHAT_RESULTS, "text": txt, "parse_mode": "HTML"}
        )
    except:
        pass

def load_coupons():
    if not os.path.exists(COUPONS_FILE):
        return []
    try:
        with open(COUPONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def run_weekly_report():
    coupons = load_coupons()
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)

    week = []
    for c in coupons:
        try:
            dt = datetime.fromisoformat(c["date"])
            if dt >= week_ago and c.get("status") in ("WON", "LOST"):
                week.append(c)
        except:
            continue

    if not week:
        send_msg("📊 RAPORT TYGODNIOWY\nBrak rozliczonych zakładów w ostatnich 7 dniach.")
        return

    total = len(week)
    won = sum(1 for c in week if c["status"] == "WON")
    lost = total - won

    profit = 0
    for c in week:
        if c["status"] == "WON":
            profit += (c["stake"] * c["odds"]) - c["stake"]
        else:
            profit -= c["stake"]

    acc = (won / total) * 100 if total else 0

    leagues = defaultdict(list)
    for c in week:
        leagues[c["league_name"]].append(c)

    ranking = []
    for league, lst in leagues.items():
        l_profit = 0
        l_stake = 0
        for c in lst:
            l_stake += c["stake"]
            if c["status"] == "WON":
                l_profit += (c["stake"] * c["odds"]) - c["stake"]
            else:
                l_profit -= c["stake"]

        roi = (l_profit / l_stake) * 100 if l_stake else 0
        ranking.append((league, len(lst), l_profit, roi))

    ranking.sort(key=lambda x: x[2], reverse=True)

    msg = (
        "📊 <b>RAPORT TYGODNIOWY (NO TAX)</b>\n"
        "📅 Ostatnie 7 dni\n\n"
        f"Zakłady: <b>{total}</b>\n"
        f"✅ Wygrane: <b>{won}</b>\n"
        f"❌ Przegrane: <b>{lost}</b>\n"
        f"🎯 Skuteczność: <b>{acc:.1f}%</b>\n"
        f"💰 Wynik: <b>{profit:.2f} zł</b>\n\n"
        "🏆 <b>RANKING LIG:</b>\n"
    )

    for i, (l, cnt, p, roi) in enumerate(ranking, 1):
        msg += f"{i}️⃣ {l} | Bets: {cnt} | 💰 {p:.2f} zł | ROI: {roi:.1f}%\n"

    send_msg(msg)

if __name__ == "__main__":
    run_weekly_report()