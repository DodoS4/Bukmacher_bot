import json
import os
from collections import defaultdict
from datetime import datetime, timezone
import requests

# ================= CONFIG =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS")
COUPONS_FILE = "coupons.json"

# ================= LEAGUE INFO =================
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
    stats = defaultdict(lambda: {"total":0,"won":0,"lost":0,"pending":0})
    for c in coupons:
        if c.get("type") != "value":
            continue
        league = c.get("league", "unknown")
        stats[league]["total"] += 1
        if c.get("status") == "won":
            stats[league]["won"] += 1
        elif c.get("status") == "lost":
            stats[league]["lost"] += 1
        else:
            stats[league]["pending"] += 1
    return stats

def format_stats(stats):
    msg = ""
    for league, data in stats.items():
        name = LEAGUE_INFO.get(league, {"name": league, "flag": "🎯"})["name"]
        flag = LEAGUE_INFO.get(league, {"name": league, "flag": "🎯"})["flag"]
        total_played = data["won"] + data["lost"]
        pct = round((data["won"]/total_played)*100,2) if total_played > 0 else 0.0
        msg += f"{flag} {name}: {data['total']} meczów | 🟢 Wygrane {data['won']} | 🔴 Przegrane {data['lost']} | ⏳ Pending {data['pending']} | 💎 Skuteczność: {pct}%\n"
    return msg

# ================= MAIN =================
def main():
    coupons = load_json(COUPONS_FILE, [])
    now = datetime.now(timezone.utc).date()
    
    if not coupons:
        send_msg(f"📊 Statystyki dzienne - Value Bets | {now}\nBrak kuponów do analizy.")
        return

    stats = calc_stats(coupons)
    msg = f"📊 Statystyki dzienne - Value Bets | {now}\n\n{format_stats(stats)}"
    send_msg(msg)

if __name__ == "__main__":
    main()