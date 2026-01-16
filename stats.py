import json
import os
import requests
from datetime import datetime

# Konfiguracja
HISTORY_FILE = "history.json"
BANKROLL_FILE = "bankroll.json"
TELEGRAM_TOKEN = os.getenv("T_TOKEN")
TELEGRAM_CHAT = os.getenv("T_CHAT_RESULTS")

def send_telegram_with_photo(message, photo_url):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    payload = {"chat_id": TELEGRAM_CHAT, "photo": photo_url, "caption": message, "parse_mode": "HTML"}
    requests.post(url, json=payload)

def generate_chart_url(balance_history):
    chart_config = {
        "type": "line",
        "data": {
            "labels": [f"T{i}" for i in range(len(balance_history))],
            "datasets": [{
                "label": "Bankroll PLN",
                "data": balance_history,
                "borderColor": "#00ff88",
                "backgroundColor": "rgba(0, 255, 136, 0.1)",
                "fill": True,
                "borderWidth": 3,
                "pointRadius": 2
            }]
        },
        "options": {
            "title": {"display": True, "text": "PROGRES TWOJEGO KAPITAŁU", "fontColor": "#fff"},
            "legend": {"labels": {"fontColor": "#fff"}},
            "scales": {
                "yAxes": [{"ticks": {"fontColor": "#ccc"}}],
                "xAxes": [{"ticks": {"fontColor": "#ccc"}}]
            }
        }
    }
    return f"https://quickchart.io/chart?c={json.dumps(chart_config)}&bkg=rgb(30,30,30)"

def generate_stats():
    if not os.path.exists(HISTORY_FILE): return
    with open(HISTORY_FILE, "r", encoding="utf-8") as f: history = json.load(f)
    if not history: return

    # Obliczenia
    total_profit = sum(x['profit'] for x in history)
    wins = [x for x in history if x['win']]
    win_rate = (len(wins) / len(history)) * 100
    
    avg_odds = sum(x['odds'] for x in history) / len(history)
    avg_win_odds = sum(x['odds'] for x in wins) / len(wins) if wins else 0
    
    # Historia bankrolla do wykresu
    current_br = 1000.0 # Startowy
    balance_history = [current_br]
    for x in history:
        current_br += x['profit']
        balance_history.append(round(current_br, 2))

    # Budowanie wiadomości
    msg = (
        f"🏆 <b>RAPORT ANALITYCZNY</b>\n"
        f"📅 <i>Stan na: {datetime.now().strftime('%d.%m | %H:%M')}</i>\n"
        f"<code>━━━━━━━━━━━━━━━━━━</code>\n\n"
        f"🎯 Skuteczność: <b>{win_rate:.1f}%</b>\n"
        f"💰 Całkowity zysk: <b>{total_profit:+.2f} PLN</b>\n\n"
        f"📊 <b>STATYSTYKI KURSÓW:</b>\n"
        f"🔹 Średni kurs typów: <b>{avg_odds:.2f}</b>\n"
        f"✅ Średni kurs trafiony: <b>{avg_win_odds:.2f}</b>\n\n"
        f"💰 <b>Obecny Bankroll: {balance_history[-1]:.2f} PLN</b>"
    )

    chart_url = generate_chart_url(balance_history)
    send_telegram_with_photo(msg, chart_url)

if __name__ == "__main__":
    generate_stats()
