import json
import os
import requests
from datetime import datetime

# ================= KONFIGURACJA =================
HISTORY_FILE = "history.json"
TELEGRAM_TOKEN = os.getenv("T_TOKEN")
TELEGRAM_CHAT = os.getenv("T_CHAT")

def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT:
        print(message) # Jeśli brak tokenów, wypisz w konsoli
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": TELEGRAM_CHAT, "text": message, "parse_mode": "HTML"})

def load_json(file, default):
    if os.path.exists(file):
        with open(file, "r", encoding="utf-8") as f:
            try: return json.load(f)
            except: return default
    return default

def generate_full_report():
    history = load_json(HISTORY_FILE, [])
    
    if not history:
        send_telegram("⚠️ <b>Brak danych w historii</b> do wygenerowania raportu.")
        return

    monthly_stats = {} 
    sport_stats = {}   
    total_bets = len(history)
    total_profit = 0
    wins = 0

    for bet in history:
        dt = datetime.fromisoformat(bet['time'].replace("Z", "+00:00"))
        month_key = dt.strftime("%Y-%m")
        
        profit = bet['profit']
        total_profit += profit
        if profit > 0: wins += 1
        
        # Statystyki miesięczne
        monthly_stats[month_key] = monthly_stats.get(month_key, 0) + profit
        
        # Statystyki dyscyplin
        sport = bet.get('sport', 'INNE').replace('soccer_', '').replace('icehockey_', '').replace('basketball_', '').upper()
        sport_stats[sport] = sport_stats.get(sport, 0) + profit

    # Budowanie wiadomości
    msg = "📜 <b>PEŁNY RAPORT WYNIKÓW</b>\n"
    msg += "━━━━━━━━━━━━━━━━━━\n"
    msg += f"💰 Zysk całkowity: <b>{total_profit:.2f} PLN</b>\n"
    msg += f"📈 Skuteczność: <b>{(wins/total_bets)*100:.1f}%</b> ({wins}/{total_bets})\n"
    msg += "━━━━━━━━━━━━━━━━━━\n\n"

    msg += "🗓 <b>ZYSKI PO MIESIĄCACH:</b>\n"
    for month in sorted(monthly_stats.keys()):
        val = monthly_stats[month]
        icon = "🟢" if val >= 0 else "🔴"
        msg += f"{icon} {month}: <b>{val:+.2f} PLN</b>\n"

    msg += "\n🏆 <b>RANKING DYSCYPLIN:</b>\n"
    sorted_sports = sorted(sport_stats.items(), key=lambda x: x[1], reverse=True)
    for sport, val in sorted_sports:
        msg += f"🔹 {sport}: <b>{val:+.2f} PLN</b>\n"
    
    msg += "━━━━━━━━━━━━━━━━━━"
    
    send_telegram(msg)

if __name__ == "__main__":
    generate_full_report()
