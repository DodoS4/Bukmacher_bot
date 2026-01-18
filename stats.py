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
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT, "text": message, "parse_mode": "HTML"})
    except: pass

def analyze_stats():
    if not os.path.exists(HISTORY_FILE): return
    
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        history = json.load(f)
    
    if not os.path.exists(BANKROLL_FILE):
        br_data = {"bankroll": 0.0}
    else:
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
        streak_msg = f"🔥 <b>GORĄCA SERIA: {streak} WYGRANE!</b> 🔥\n"
        streak_msg += f"━━━━━━━━━━━━━━━━━━\n"
        streak_msg += f"System właśnie rozbił bank! 🚀"
        send_telegram(streak_msg)

    # --- 2. RANKING LIG (NOWOŚĆ) ---
    league_map = {}
    for bet in history:
        l_name = bet.get('sport', 'Inne').replace('soccer_', '').replace('icehockey_', '').upper()
        league_map[l_name] = league_map.get(l_name, 0) + bet.get('profit', 0)
    
    # Sortowanie lig od najlepszej
    sorted_leagues = sorted(league_map.items(), key=lambda x: x[1], reverse=True)
    ranking_str = ""
    for i, (name, prof) in enumerate(sorted_leagues[:3]): # Top 3 ligi
        emoji = "🥇" if i == 0 else "🥈" if i == 1 else "🥉"
        ranking_str += f"{emoji} {name}: <b>{prof:+.2f}</b>\n"

    # --- 3. RAPORT OGÓLNY ---
    total_profit = sum([b['profit'] for b in history])
    total_turnover = sum([b.get('stake', 250) for b in history])
    yield_val = (total_profit / total_turnover) * 100 if total_turnover > 0 else 0
    
    progress_pct = (total_profit / MONTHLY_TARGET) * 100
    progress_bar = "▓" * int(min(max(progress_pct, 0), 100) / 10) + "░" * (10 - int(min(max(progress_pct, 0), 100) / 10))

    msg = f"📈 <b>RAPORT ZYSKÓW</b>\n"
    msg += f"━━━━━━━━━━━━━━━━━━\n"
    msg += f"💰 Zysk netto: <b>{total_profit:+.2f} PLN</b>\n"
    msg += f"📊 Yield: <b>{yield_val:.2f}%</b>\n"
    msg += f"🏦 Bankroll: <b>{br_data['bankroll']:.2f} PLN</b>\n\n"
    msg += f"🏆 <b>TOP LIGI:</b>\n{ranking_str}\n"
    msg += f"🎯 Cel {MONTHLY_TARGET} PLN:\n"
    msg += f"<code>[{progress_bar}] {progress_pct:.1f}%</code>"
    
    send_telegram(msg)

if __name__ == "__main__":
    analyze_stats()
