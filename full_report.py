import json
import os
import requests
from datetime import datetime

# ================= KONFIGURACJA =================
HISTORY_FILE = "history.json"
TELEGRAM_TOKEN = os.getenv("T_TOKEN")
TELEGRAM_CHAT = os.getenv("T_CHAT_RESULTS") or os.getenv("T_CHAT")

def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": TELEGRAM_CHAT, "text": message, "parse_mode": "HTML"})

def generate_report():
    if not os.path.exists(HISTORY_FILE):
        return
    
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        history = json.load(f)
    
    if not history:
        send_telegram("⚠️ Brak danych do raportu!")
        return

    # --- OBLICZENIA OGÓLNE ---
    total_profit = sum(item['profit'] for item in history)
    win_count = sum(1 for item in history if item['profit'] > 0)
    total_matches = len(history)
    win_rate = (win_count / total_matches) * 100

    # --- OBLICZENIA DZIŚ ---
    today_str = datetime.now().strftime("%Y-%m-%d")
    # Filtrujemy mecze, których data zaczyna się od dzisiejszego dnia
    today_matches = [item for item in history if item['time'].startswith(today_str)]
    today_profit = sum(item['profit'] for item in today_matches)

    # Grupowanie po miesiącach i dyscyplinach
    monthly = {}
    leagues = {}
    for item in history:
        m = item['time'][:7]
        monthly[m] = monthly.get(m, 0) + item['profit']
        
        sport = item.get('sport', 'Inne').replace("soccer_", "").replace("_", " ").upper()
        leagues[sport] = leagues.get(sport, 0) + item['profit']

    # --- BUDOWANIE WIADOMOŚCI ---
    msg = f"📜 <b>PEŁNY RAPORT WYNIKÓW</b>\n"
    msg += f"━━━━━━━━━━━━━━━━━━\n"
    msg += f"💰 Zysk całkowity: <b>{total_profit:+.2f} PLN</b>\n"
    msg += f"📈 Skuteczność: <b>{win_rate:.1f}%</b> ({win_count}/{total_matches})\n"
    
    # Wyświetl wynik dzisiejszy tylko jeśli były jakieś mecze
    status_emoji = "🟢" if today_profit >= 0 else "🔴"
    msg += f"📅 <b>DZISIAJ ({datetime.now().strftime('%d.%m')}):</b> <b>{today_profit:+.2f} PLN</b> {status_emoji}\n"
    msg += f"━━━━━━━━━━━━━━━━━━\n\n"

    msg += f"🗓 <b>ZYSKI PO MIESIĄCACH:</b>\n"
    for m, p in sorted(monthly.items(), reverse=True):
        emoji = "🟢" if p >= 0 else "🔴"
        msg += f"{emoji} {m}: <b>{p:+.2f} PLN</b>\n"

    msg += f"\n🏆 <b>RANKING DYSCYPLIN:</b>\n"
    for l, p in sorted(leagues.items(), key=lambda x: x[1], reverse=True):
        emoji = "🔹" if p >= 0 else "🔸"
        msg += f"{emoji} {l}: <b>{p:+.2f} PLN</b>\n"

    msg += f"\n👋 <i>Powodzenia w kolejnych typach!</i>"

    send_telegram(msg)

if __name__ == "__main__":
    generate_report()
