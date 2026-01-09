import json
import os
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from dateutil import parser
import requests

# ================= CONFIG =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT_RESULTS")  # statystyki wysyłamy do wyników

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
    if not T_TOKEN or not T_CHAT:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
            json={
                "chat_id": T_CHAT,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            },
            timeout=10
        )
    except:
        pass

# ================= STATS =================
def calc_stats(coupons, type_filter=None):
    stats = defaultdict(lambda: {"types":0,"won":0,"lost":0})
    for c in coupons:
        if type_filter and c.get("type") != type_filter:
            continue
        stats[c["league"]]["types"] += 1
        stats[c["league"]]["won"] += c.get("win_val",0)
        if c["status"]=="lost":
            stats[c["league"]]["lost"] += c.get("stake",0)
    return stats

def format_stats(stats_dict):
    msg=""
    for league, data in stats_dict.items():
        profit = data["won"] - data["lost"]
        msg += f"{league}: Typów {data['types']} | 🟢 Wygrane {round(data['won'],2)} | 🔴 Przegrane {round(data['lost'],2)} | 💎 Zysk {round(profit,2)}\n"
    return msg

def main():
    coupons = load_json(COUPONS_FILE, [])

    if not coupons:
        send_msg("📊 Brak rozliczonych kuponów do analizy.")
        return

    now = datetime.now(timezone.utc)

    # --- Statystyki dzienne ---
    today_coupons = [c for c in coupons if c.get("sent_date")==str(now.date())]
    if today_coupons:
        value_stats = format_stats(calc_stats(today_coupons, "value"))
        btts_stats = format_stats(calc_stats(today_coupons, "btts_over"))
        send_msg(f"📊 <b>Statystyki dzienne</b> | {str(now.date())}\n\n<b>VALUE Bets:</b>\n{value_stats}\n<b>BTTS/Over:</b>\n{btts_stats}")

    # --- Statystyki tygodniowe ---
    if now.weekday()==6:  # niedziela
        week_coupons = [c for c in coupons if parser.isoparse(c.get("sent_date")).isocalendar()[1]==now.isocalendar()[1]]
        if week_coupons:
            value_stats = format_stats(calc_stats(week_coupons, "value"))
            btts_stats = format_stats(calc_stats(week_coupons, "btts_over"))
            send_msg(f"📊 <b>Statystyki tygodniowe</b> | tydzień {now.isocalendar()[1]}\n\n<b>VALUE Bets:</b>\n{value_stats}\n<b>BTTS/Over:</b>\n{btts_stats}")

    # --- Statystyki miesięczne ---
    tomorrow = now + timedelta(days=1)
    if tomorrow.day == 1:  # ostatni dzień miesiąca
        month_coupons = [c for c in coupons if parser.isoparse(c.get("sent_date")).month==now.month]
        if month_coupons:
            value_stats = format_stats(calc_stats(month_coupons, "value"))
            btts_stats = format_stats(calc_stats(month_coupons, "btts_over"))
            send_msg(f"📊 <b>Statystyki miesięczne</b> | miesiąc {now.month}\n\n<b>VALUE Bets:</b>\n{value_stats}\n<b>BTTS/Over:</b>\n{btts_stats}")

if __name__ == "__main__":
    main()