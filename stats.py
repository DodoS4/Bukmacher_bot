import json
import os
from collections import defaultdict
from datetime import datetime, timezone
from dateutil import parser
import requests

# ================= CONFIG =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS")
COUPONS_FILE = "coupons.json"

LEAGUE_INFO = {
    "basketball_nba": {"name": "NBA", "flag": "🏀"},
    "icehockey_nhl": {"name": "NHL", "flag": "🏒"},
    "soccer_epl": {"name": "Premier League", "flag": "⚽"},
    "soccer_poland_ekstraklasa": {"name": "Ekstraklasa", "flag": "⚽"},
    "soccer_uefa_champs_league": {"name": "Champions League", "flag": "🏆"}
}

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
def send_stats():
    coupons = load_json(COUPONS_FILE, [])
    now = datetime.now(timezone.utc)

    stats = defaultdict(lambda: {"total":0,"won":0,"lost":0,"pending":0,"profit":0})

    for c in coupons:
        if c.get("type")!="value":
            continue
        league = c["league"]
        stats[league]["total"] += 1
        if c["status"]=="won":
            stats[league]["won"] += 1
            stats[league]["profit"] += c.get("win_val",0)
        elif c["status"]=="lost":
            stats[league]["lost"] += 1
            stats[league]["profit"] -= c.get("stake",0)
        else:
            stats[league]["pending"] += 1

    total_profit = 0
    msg_lines = []
    for league, data in stats.items():
        total = data["total"]
        won = data["won"]
        lost = data["lost"]
        pending = data["pending"]
        profit = data["profit"]
        total_profit += profit
        try:
            success = round((won/total)*100,1) if total>0 else 0
        except:
            success = 0
        info = LEAGUE_INFO.get(league, {"name": league, "flag": "🎯"})
        line = (
            f"{info['flag']} {info['name']}: {total} mecze{'w' if total>1 else ''} | "
            f"🟢 {won} | 🔴 {lost} | ⏳ {pending} | "
            f"💎 Skuteczność: {success}% | 💰 Zysk: {round(profit,2)} PLN"
        )
        msg_lines.append(line)

    msg = "\n".join(msg_lines)
    msg += f"\n\n💰 Łączny zysk wszystkich lig: {round(total_profit,2)} PLN"
    send_msg(f"📊 Statystyki dzienne - Value Bets | {str(now.date())}\n\n{msg}")

# ================= MAIN =================
if __name__=="__main__":
    send_stats()