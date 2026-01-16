import json
import os
import requests
from datetime import datetime

# Konfiguracja
HISTORY_FILE = "history.json"
TELEGRAM_TOKEN = os.getenv("T_TOKEN")
TELEGRAM_CHAT = os.getenv("T_CHAT_RESULTS")

def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT, "text": message, "parse_mode": "HTML"})
    except:
        pass

def generate_stats():
    if not os.path.exists(HISTORY_FILE): return

    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        history = json.load(f)

    if not history: return

    stats_by_sport = {}
    for x in history:
        sport = x.get("sport", "Inne").replace("Soccer", "Piłka").replace("Basketball", "Kosz")
        if sport not in stats_by_sport:
            stats_by_sport[sport] = {"wins": 0, "total": 0, "profit": 0.0}
        
        stats_by_sport[sport]["total"] += 1
        stats_by_sport[sport]["profit"] += x["profit"]
        if x["win"]: stats_by_sport[sport]["wins"] += 1

    # Sortowanie lig od najlepszej
    sorted_sports = sorted(stats_by_sport.items(), key=lambda item: item[1]['profit'], reverse=True)

    # Budowanie nagłówka
    msg = "🏆 <b>RANKING SKUTECZNOŚCI LIG</b>\n"
    msg += f"📅 <i>Stan na: {datetime.now().strftime('%d.%m | %H:%M')}</i>\n"
    msg += "<code>━━━━━━━━━━━━━━━━━━</code>\n\n"

    for i, (sport, data) in enumerate(sorted_sports):
        wr = (data["wins"] / data["total"]) * 100
        profit = data["profit"]
        
        # Ikony miejsc
        rank_icon = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else "🔹"
        trend = "📈" if profit >= 0 else "📉"
        
        msg += f"{rank_icon} <b>{sport.upper()}</b>\n"
        msg += f"<blockquote>"
        msg += f"Skuteczność: <b>{wr:.1f}%</b> ({data['wins']}/{data['total']})\n"
        msg += f"Zysk netto:  <b>{profit:+.2f} PLN</b> {trend}"
        msg += f"</blockquote>\n"

    # Podsumowanie ogólne
    total_profit = sum(x['profit'] for x in history)
    total_bets = len(history)
    overall_wr = (sum(1 for x in history if x['win']) / total_bets) * 100
    
    msg += "<code>━━━━━━━━━━━━━━━━━━</code>\n"
    msg += f"📊 <b>PODSUMOWANIE OGÓLNE</b>\n"
    msg += f"📦 Wszystkie typy: <b>{total_bets}</b>\n"
    msg += f"🎯 Skuteczność: <b>{overall_wr:.1f}%</b>\n"
    msg += f"💰 Łączny profit: <u><b>{total_profit:+.2f} PLN</b></u>"

    send_telegram(msg)

if __name__ == "__main__":
    generate_stats()
