import json
import os
import requests

# ================= KONFIGURACJA =================
HISTORY_FILE = "history.json"
BANKROLL_FILE = "bankroll.json"
TELEGRAM_TOKEN = os.getenv("T_TOKEN")
TELEGRAM_CHAT = os.getenv("T_CHAT_RESULTS") or os.getenv("T_CHAT")
MONTHLY_TARGET = 5000.0

def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": TELEGRAM_CHAT, "text": message, "parse_mode": "HTML"})

def analyze_stats():
    if not os.path.exists(HISTORY_FILE): return
    
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        history = json.load(f)
    with open(BANKROLL_FILE, "r", encoding="utf-8") as f:
        br_data = json.load(f)
    
    if not history: return

    # --- 1. LOGIKA GORĄCEJ SERII ---
    streak = 0
    for bet in reversed(history):
        if bet.get('profit', 0) > 0:
            streak += 1
        else:
            break
    
    if streak >= 3:
        streak_msg = f"🔥 <b>GORĄCA SERIA: {streak} WYGRANE Z RZĘDU!</b> 🔥\n"
        streak_msg += f"━━━━━━━━━━━━━━━━━━\n"
        streak_msg += f"Twoja strategia aktualnie dominuje na rynku! 🚀"
        send_telegram(streak_msg)

    # --- 2. ALERT REKORDOWEGO KURSU ---
    last_bet = history[-1]
    if last_bet.get('profit', 0) > 0:
        # Znajdź najwyższy kurs ze wszystkich poprzednich wygranych meczów
        all_winning_odds = [b.get('odds', 0) for b in history[:-1] if b.get('profit', 0) > 0]
        max_prev_odds = max(all_winning_odds) if all_winning_odds else 0
        
        if last_bet.get('odds', 0) > max_prev_odds and max_prev_odds > 0:
            record_msg = f"🏆 <b>NOWY REKORD KURSU!</b> 🏆\n"
            record_msg += f"━━━━━━━━━━━━━━━━━━\n"
            record_msg += f"Trafiony kurs: <b>{last_bet['odds']:.2f}</b>\n"
            record_msg += f"Poprzedni rekord: {max_prev_odds:.2f}\n"
            record_msg += f"Mecz: {last_bet['home']} - {last_bet['away']}"
            send_telegram(record_msg)

    # --- 3. RAPORT OGÓLNY ---
    total_profit = sum([b['profit'] for b in history])
    total_turnover = sum([b.get('stake', 250) for b in history])
    yield_val = (total_profit / total_turnover) * 100 if total_turnover > 0 else 0
    
    progress_pct = (total_profit / MONTHLY_TARGET) * 100
    progress_bar = "▓" * int(min(max(progress_pct, 0), 100) / 10) + "░" * (10 - int(min(max(progress_pct, 0), 100) / 10))

    msg = f"📈 <b>STATUS PROJEKTU 5000</b>\n"
    msg += f"━━━━━━━━━━━━━━━━━━\n"
    msg += f"💰 Zysk netto: <b>{total_profit:+.2f} PLN</b>\n"
    msg += f"📊 Yield: <b>{yield_val:.2f}%</b>\n"
    msg += f"🏦 Bankroll: <b>{br_data['bankroll']:.2f} PLN</b>\n\n"
    msg += f"🎯 Postęp: <b>{progress_pct:.1f}%</b>\n"
    msg += f"<code>[{progress_bar}]</code>"
    
    send_telegram(msg)

if __name__ == "__main__":
    analyze_stats()
