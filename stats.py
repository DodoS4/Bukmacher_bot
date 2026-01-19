import json
import os
import requests
from datetime import datetime

# ================= KONFIGURACJA =================
HISTORY_FILE = "history.json"
BANKROLL_FILE = "bankroll.json"
TELEGRAM_TOKEN = os.getenv("T_TOKEN")
TELEGRAM_CHAT = os.getenv("T_CHAT_RESULTS") or os.getenv("T_CHAT")
MONTHLY_TARGET = 5000.0

def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT, "text": message, "parse_mode": "HTML"})
    except: pass

def analyze_stats():
    if not os.path.exists(HISTORY_FILE): 
        print("Brak historii.")
        return
    
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        history = json.load(f)
    
    br_data = {"bankroll": 0.0}
    if os.path.exists(BANKROLL_FILE):
        with open(BANKROLL_FILE, "r", encoding="utf-8") as f:
            br_data = json.load(f)
    
    if not history: return

    # --- 1. RANKING LIG ---
    league_stats = {}
    for bet in history:
        l_name = bet.get('sport', 'Inne').replace('soccer_', '').replace('icehockey_', '').upper()
        if l_name not in league_stats:
            league_stats[l_name] = {'profit': 0.0, 'bets': 0}
        league_stats[l_name]['profit'] += bet.get('profit', 0)
        league_stats[l_name]['bets'] += 1
    
    # Sortowanie lig od najlepszej (Top 5)
    sorted_leagues = sorted(league_stats.items(), key=lambda x: x[1]['profit'], reverse=True)
    
    ranking_str = ""
    for i, (name, data) in enumerate(sorted_leagues[:5]):
        emoji = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else "🔹"
        ranking_str += f"{emoji} {name}: <b>{data['profit']:+.2f} PLN</b>\n"

    # --- 2. ANALIZA OGÓLNA ---
    total_net_profit = sum([b['profit'] for b in history])
    total_turnover = sum([b.get('stake', 250) for b in history])
    yield_val = (total_net_profit / total_turnover) * 100 if total_turnover > 0 else 0
    
    # --- 3. PROGRES I RAPORT ---
    progress_pct = (total_net_profit / MONTHLY_TARGET) * 100
    progress_bar_count = int(min(max(progress_pct, 0), 100) / 10)
    progress_bar = "▓" * progress_bar_count + "░" * (10 - progress_bar_count)

    msg = f"📈 <b>RAPORT ZYSKÓW</b>\n"
    msg += f"━━━━━━━━━━━━━━━━━━\n"
    msg += f"💰 Zysk na czysto: <b>{total_net_profit:+.2f} PLN</b>\n"
    msg += f"📊 Yield: <b>{yield_val:.2f}%</b>\n"
    msg += f"🏦 Bankroll: <b>{br_data['bankroll']:.2f} PLN</b>\n"
    msg += f"━━━━━━━━━━━━━━━━━━\n"
    msg += f"🏆 <b>NAJLEPSZE LIGI:</b>\n{ranking_str}\n"
    msg += f"🎯 Cel {MONTHLY_TARGET} PLN:\n"
    msg += f"<code>[{progress_bar}] {progress_pct:.1f}%</code>"
    
    send_telegram(msg)

if __name__ == "__main__":
    analyze_stats()
