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
    if not os.path.exists(HISTORY_FILE):
        print("Brak pliku historii.")
        return

    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        history = json.load(f)

    if not history:
        print("Historia jest pusta.")
        return

    total_bets = len(history)
    wins = sum(1 for x in history if x["win"])
    losses = total_bets - wins
    win_rate = (wins / total_bets) * 100 if total_bets > 0 else 0
    
    total_profit = sum(x["profit"] for x in history)
    
    # Obliczanie Yield (Zysk / Suma stawek)
    # Zakładając stałą stawkę dla uproszczenia statystyk lub sumując realne stawki
    # Tutaj przyjmiemy sumę bezwzględnych wartości strat i kosztów wygranych
    total_staked = sum(abs(x["profit"] / (1.70 - 1)) if x["win"] else abs(x["profit"]) for x in history) # Przybliżenie
    yield_val = (total_profit / total_staked) * 100 if total_staked > 0 else 0

    # Budowanie raportu
    status_icon = "📈" if total_profit >= 0 else "📉"
    
    report = (
        f"📊 <b>RAPORT SKUTECZNOŚCI</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"✅ Trafione: <b>{wins}</b>\n"
        f"❌ Przegrane: <b>{losses}</b>\n"
        f"🎯 Skuteczność: <b>{win_rate:.1f}%</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"💰 Całkowity zysk: <b>{total_profit:+.2f} PLN</b>\n"
        f"{status_icon} Yield: <b>{yield_val:+.2f}%</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"<i>Ostatnia aktualizacja: {datetime.now().strftime('%d.%m %H:%M')}</i>"
    )

    send_telegram(report)
    print("Statystyki wysłane na Telegram.")

if __name__ == "__main__":
    generate_stats()
