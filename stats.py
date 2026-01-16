import json
import os
import requests
from datetime import datetime

HISTORY_FILE = "history.json"
TELEGRAM_TOKEN = os.getenv("T_TOKEN")
TELEGRAM_CHAT = os.getenv("T_CHAT_RESULTS")

def generate_stats():
    if not os.path.exists(HISTORY_FILE): return
    with open(HISTORY_FILE, "r") as f: history = json.load(f)
    if not history: return

    # Obliczenia
    total_profit = sum(x['profit'] for x in history)
    current_br = 1000.0
    br_history = [current_br]
    for x in history:
        current_br += x['profit']
        br_history.append(round(current_br, 2))

    # Wykres
    chart_cfg = {"type":"line","data":{"labels":[f"T{i}" for i in range(len(br_history))],"datasets":[{"label":"Bankroll","data":br_history,"borderColor":"#00ff88","fill":False}]}}
    chart_url = f"https://quickchart.io/chart?c={json.dumps(chart_cfg)}&bkg=rgb(30,30,30)"

    # Wiadomość
    msg = f"🏆 <b>RAPORT ANALITYCZNY</b>\n<code>━━━━━━━━━━━━━━━━━━</code>\n"
    msg += f"🎯 Skuteczność: <b>{(sum(1 for x in history if x['win'])/len(history))*100:.1f}%</b>\n"
    msg += f"💰 Profit: <b>{total_profit:+.2f} PLN</b>\n"
    msg += f"💹 Średni kurs: <b>{sum(x['odds'] for x in history)/len(history):.2f}</b>\n"
    msg += f"<code>━━━━━━━━━━━━━━━━━━</code>"

    requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto", json={"chat_id": TELEGRAM_CHAT, "photo": chart_url, "caption": msg, "parse_mode": "HTML"})

if __name__ == "__main__":
    generate_stats()
