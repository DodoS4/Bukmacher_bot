import json
import os
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from dateutil import parser
import requests

# ================= CONFIG =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS")
COUPONS_FILE = "coupons.json"

LEAGUE_INFO = {
    "basketball_nba": {"name": "NBA", "flag": "🏀"},
    "soccer_epl": {"name": "Premier League", "flag": "⚽ PL"},
    "icehockey_nhl": {"name": "NHL", "flag": "🏒"},
    "soccer_poland_ekstraklasa": {"name": "Ekstraklasa", "flag": "⚽ EK"},
    "soccer_uefa_champs_league": {"name": "Champions League", "flag": "🏆 CL"}
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
def calc_stats(coupons):
    stats = defaultdict(lambda: {"matches": 0, "won": 0, "lost": 0, "profit": 0})
    for c in coupons:
        league = c["league"]
        stats[league]["matches"] += 1
        if c["status"] == "won":
            stats[league]["won"] += 1
            stats[league]["profit"] += c.get("win_val", 0)
        elif c["status"] == "lost":
            stats[league]["lost"] += 1
            stats[league]["profit"] -= c.get("stake", 0)
    return stats

def format_stats(stats_dict):
    msg = ""
    for league, data in stats_dict.items():
        matches = data["matches"]
        won = data["won"]
        lost = data["lost"]
        profit = round(data["profit"], 2)
        success_pct = round((won/matches)*100, 1) if matches else 0
        info = LEAGUE_INFO.get(league, {"name": league, "flag": "🎯"})
        msg += (f"{info['flag']} {info['name']}: Mecze {matches} | 🟢 {won} | 🔴 {lost} | "
                f"💎 {profit} PLN | ✅ {success_pct}%\n")
    return msg

def main():
    coupons = load_json(COUPONS_FILE, [])

    if not coupons:
        send_msg("📊 Brak rozliczonych kuponów do analizy.")
        return

    now = datetime.now(timezone.utc)

    # --- Statystyki dzienne ---
    today_coupons = [c for c in coupons if c.get("sent_date") == str(now.date())]
    if today_coupons:
        send_msg(f"📊 Statystyki dzienne - Value Bets | {now.date()}\n\n{format_stats(today_coupons)}")

    # --- Statystyki tygodniowe ---
    week_number = now.isocalendar()[1]
    week_coupons = [c for c in coupons if parser.isoparse(c.get("sent_date")).isocalendar()[1] == week_number]
    if week_coupons:
        send_msg(f"📊 Statystyki tygodniowe - Value Bets | tydzień {week_number}\n\n{format_stats(week_coupons)}")

    # --- Statystyki miesięczne ---
    month = now.month
    month_coupons = [c for c in coupons if parser.isoparse(c.get("sent_date")).month == month]
    if month_coupons:
        send_msg(f"📊 Statystyki miesięczne - Value Bets | miesiąc {month}\n\n{format_stats(month_coupons)}")

if __name__ == "__main__":
    main()