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

    # --- 1. FILTROWANIE I ANALIZA (IGNORUJEMY REMISY) ---
    league_stats = {}
    total_net_profit = 0.0
    total_turnover = 0.0
    total_wins = 0
    valid_bets_count = 0

    for bet in history:
        # KLUCZOWE: Całkowicie pomijamy remisy w raporcie
        if bet.get('outcome') == 'Draw':
            continue

        valid_bets_count += 1
        profit = bet.get('profit', 0)
        total_net_profit += profit
        total_turnover += bet.get('stake', 250)
        
        if bet.get('status') == 'WIN':
            total_wins += 1

        # Statystyki lig (czyszczenie nazw)
        l_raw = bet.get('sport', 'Inne')
        l_name = l_raw.replace('soccer_', '').replace('icehockey_', '').replace('_', ' ').upper()
        
        if l_name not in league_stats:
            league_stats[l_name] = {'profit': 0.0, 'bets': 0}
        league_stats[l_name]['profit'] += profit
        league_stats[l_name]['bets'] += 1
    
    if valid_bets_count == 0:
        print("Brak danych po odfiltrowaniu remisów.")
        return

    # --- 2. RANKING LIG (TOP 5) ---
    sorted_leagues = sorted(league_stats.items(), key=lambda x: x[1]['profit'], reverse=True)
    ranking_str = ""
    for i, (name, data) in enumerate(sorted_leagues[:5]):
        emoji = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else "🔹"
        ranking_str += f"{emoji} {name}: <b>{data['profit']:+.2f} PLN</b>\n"
    
    # Najsłabsza liga (do monitoringu np. NBA lub EPL)
    if len(sorted_leagues) > 5:
        worst_name, worst_data = sorted_leagues[-1]
        ranking_str += f"📉 Najsłabsza: {worst_name} (<b>{worst_data['profit']:+.2f}</b>)\n"

    # --- 3. ANALIZA OGÓLNA ---
    yield_val = (total_net_profit / total_turnover) * 100 if total_turnover > 0 else 0
    win_rate = (total_wins / valid_bets_count) * 100
    
    yield_emoji = "🟢" if yield_val > 5 else "🟡" if yield_val > 0 else "🔴"

    # --- 4. RAPORT ---
    progress_pct = (total_net_profit / MONTHLY_TARGET) * 100
    bar_display = max(0, min(100, progress_pct))
    progress_bar_count = int(bar_display / 10)
    progress_bar = "🟢" * progress_bar_count + "⚪" * (10 - progress_bar_count)

    msg = f"📊 <b>RAPORT ANALITYCZNY (STRATEGIA 1-2)</b>\n"
    msg += f"━━━━━━━━━━━━━━━━━━\n"
    msg += f"💰 Zysk netto: <b>{total_net_profit:+.2f} PLN</b>\n"
    msg += f"{yield_emoji} Yield: <b>{yield_val:.2f}%</b>\n"
    msg += f"🎯 Skuteczność: <b>{win_rate:.1f}%</b>\n"
    msg += f"🏦 Bankroll: <b>{br_data['bankroll']:.2f} PLN</b>\n"
    msg += f"━━━━━━━━━━━━━━━━━━\n"
    msg += f"🏆 <b>LIDERZY RYNKU:</b>\n{ranking_str}\n"
    msg += f"━━━━━━━━━━━━━━━━━━\n"
    msg += f"🏁 <b>CEL: {MONTHLY_TARGET} PLN</b>\n"
    msg += f"<code>{progress_bar}</code> <b>{progress_pct:.1f}%</b>\n"
    msg += f"ℹ️ <i>Statystyki uwzględniają tylko zakłady na zwycięstwo (bez remisów).</i>"
    
    send_telegram(msg)

if __name__ == "__main__":
    analyze_stats()
