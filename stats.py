import json
import os
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from dateutil import parser
import requests
import sys

# ================= CONFIG =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS")
COUPONS_FILE = "coupons.json"

# ================= FILE UTILS =================
def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return default

# ================= TELEGRAM =================
def send_msg(text):
    if not T_TOKEN or not T_CHAT_RESULTS:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
            json={
                "chat_id": T_CHAT_RESULTS,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            },
            timeout=10
        )
    except:
        pass

# ================= STATS =================
def calc_league_stats(coupons):
    stats = defaultdict(lambda: {"matches":0,"won":0,"lost":0,"profit":0})
    for c in coupons:
        if c.get("type") != "value":
            continue
        league = c.get("league","Unknown")
        stats[league]["matches"] += 1
        if c["status"]=="won":
            stats[league]["won"] += 1
            stats[league]["profit"] += c.get("win_val",0)
        elif c["status"]=="lost":
            stats[league]["lost"] += 1
            stats[league]["profit"] -= c.get("stake",0)
    return stats

def format_stats_line(stats):
    msg = ""
    for league, data in stats.items():
        matches = data["matches"]
        won = data["won"]
        lost = data["lost"]
        profit = data["profit"]
        win_pct = round((won/matches)*100,1) if matches>0 else 0
        msg += f"{league}: Mecze {matches} | 🟢 Wygrane {won} | 🔴 Przegrane {lost} | 💎 Zysk {round(profit,2)} PLN | ✅ Skuteczność {win_pct}%\n"
    return msg

def send_stats():
    coupons = load_json(COUPONS_FILE, [])
    now = datetime.now(timezone.utc)

    # --- Statystyki dzienne ---
    today_coupons = [c for c in coupons if c.get("sent_date")==str(now.date())]
    if today_coupons:
        stats = calc_league_stats(today_coupons)
        msg = format_stats_line(stats)
        send_msg(f"📊 Statystyki dzienne - Value Bets | {now.date()}\n\n{msg}")

    # --- Statystyki tygodniowe (w niedzielę) ---
    if now.weekday()==6:
        week_number = now.isocalendar()[1]
        week_coupons = [c for c in coupons if parser.isoparse(c.get("sent_date")).isocalendar()[1]==week_number]
        if week_coupons:
            stats = calc_league_stats(week_coupons)
            msg = format_stats_line(stats)
            send_msg(f"📊 Statystyki tygodniowe - Value Bets | Tydzień {week_number}\n\n{msg}")

    # --- Statystyki miesięczne (ostatni dzień miesiąca) ---
    tomorrow = now + timedelta(days=1)
    if tomorrow.day == 1:
        month_coupons = [c for c in coupons if parser.isoparse(c.get("sent_date")).month==now.month]
        if month_coupons:
            stats = calc_league_stats(month_coupons)
            msg = format_stats_line(stats)
            send_msg(f"📊 Statystyki miesięczne - Value Bets | Miesiąc {now.month}\n\n{msg}")

# ================= RUN =================
if __name__=="__main__":
    send_stats()