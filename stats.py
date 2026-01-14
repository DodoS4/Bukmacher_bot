import json
from datetime import datetime, timedelta, timezone
import os
import requests

# ================= CONFIG =================
COUPONS_FILE = "coupons.json"
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS")
T_TOKEN = os.getenv("T_TOKEN")

# ================= HELPERS =================
def load_coupons():
    try:
        with open(COUPONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def send_telegram(message):
    if not T_CHAT_RESULTS or not T_TOKEN:
        print("Brak T_CHAT_RESULTS lub T_TOKEN – nie można wysłać raportu")
        return
    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": T_CHAT_RESULTS, "text": message, "parse_mode": "HTML"})

def filter_coupons(coupons, since):
    filtered = []
    for c in coupons:
        try:
            c_date = datetime.fromisoformat(c["date"].replace("Z", "+00:00"))
            if c_date >= since:
                filtered.append(c)
        except Exception:
            continue
    return filtered

def summarize_by_league(coupons):
    summary = {}
    for c in coupons:
        league = c.get("league_name") or c.get("league", "Unknown")
        profit = c.get("profit") or 0
        if league not in summary:
            summary[league] = {"bets": 0, "won": 0, "lost": 0, "profit": 0}
        summary[league]["bets"] += 1
        if c.get("status") == "WON":
            summary[league]["won"] += 1
        elif c.get("status") == "LOST":
            summary[league]["lost"] += 1
        summary[league]["profit"] += profit
    return summary

def format_bar(profit, max_profit):
    if max_profit <= 0:
        return "░░░░░░░░░░"
    bars = int((profit / max_profit) * 10)
    return "▓" * bars + "░" * (10 - bars)

def generate_report(period_name, since, coupons):
    filtered = filter_coupons(coupons, since)
    total_bets = len(filtered)
    won = sum(1 for c in filtered if c.get("status") == "WON")
    lost = sum(1 for c in filtered if c.get("status") == "LOST")
    pending = sum(1 for c in filtered if c.get("status") not in ["WON", "LOST"])
    profit = sum(c.get("profit") or 0 for c in filtered)

    summary = summarize_by_league(filtered)
    max_profit = max((s["profit"] for s in summary.values()), default=0)

    msg = f"📊 {period_name}\n"
    msg += "━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"🏆 Łącznie zakładów: {total_bets}\n"
    msg += f"✅ Wygrane: {won}\n"
    msg += f"❌ Przegrane: {lost}\n"
    msg += f"⏳ Pending: {pending}\n"
    msg += f"💰 Zysk/Strata: {'+' if profit>=0 else ''}{profit:.2f} zł\n"
    msg += "━━━━━━━━━━━━━━━━━━━━\n"
    msg += "📊 Rozkład na ligi:\n"

    for league, s in summary.items():
        bar = format_bar(s["profit"], max_profit)
        msg += f"{league:<18} │ Bets: {s['bets']:<3} │ ✅ {s['won']:<3} │ ❌ {s['lost']:<3} │ 💰 {'+' if s['profit']>=0 else ''}{s['profit']:.2f} zł │ {bar}\n"

    send_telegram(msg)
    print(msg)

# ================= MAIN =================
if __name__ == "__main__":
    coupons = load_coupons()
    now = datetime.now(timezone.utc)

    # Dzienny – od 7:00 UTC poprzedniego dnia
    daily_since = now.replace(hour=7, minute=0, second=0, microsecond=0) - timedelta(days=1)
    generate_report("RAPORT DZIENNY", daily_since, coupons)

    # Tygodniowy – od 7:00 UTC w zeszłą niedzielę
    weekday = now.weekday()  # 0 = poniedziałek
    days_since_sunday = (weekday + 1) % 7
    weekly_since = now.replace(hour=7, minute=0, second=0, microsecond=0) - timedelta(days=days_since_sunday)
    if now.weekday() == 6 and now.hour >= 22:  # niedziela 22:00
        generate_report("RAPORT TYGODNIOWY", weekly_since, coupons)

    # Miesięczny – od 1 dnia miesiąca
    monthly_since = now.replace(day=1, hour=7, minute=0, second=0, microsecond=0)
    if now.day == 1 and now.hour >= 7:
        generate_report("RAPORT MIESIĘCZNY", monthly_since, coupons)