import json
import os
import requests
import shutil
from datetime import datetime, timedelta

# ================= KONFIGURACJA =================
HISTORY_FILE = "history.json"
BANKROLL_FILE = "bankroll.json"
TELEGRAM_TOKEN = os.getenv("T_TOKEN")
TELEGRAM_CHAT = os.getenv("T_CHAT_RESULTS")
MONTHLY_TARGET = 5000.0  # TWÓJ CEL

def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT, "text": message, "parse_mode": "HTML"})
    except: pass

def load_json(filename, default):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            try: return json.load(f)
            except: return default
    return default

def analyze_stats():
    history = load_json(HISTORY_FILE, [])
    br_data = load_json(BANKROLL_FILE, {"bankroll": 10000.0})
    
    if not history:
        print("Brak danych do analizy.")
        return

    # --- OBLICZENIA GŁÓWNE ---
    total_profit = sum([b['profit'] for b in history])
    # Zakładamy stawkę z historii, jeśli jej nie ma, bierzemy domyślną 200 (zgodnie ze start.py)
    total_turnover = sum([b.get('stake', 200) for b in history])
    
    # YIELD: (Zysk / Obrót) * 100
    yield_val = (total_profit / total_turnover) * 100 if total_turnover > 0 else 0
    
    # PROGRES DO 5000 PLN
    progress_pct = min((total_profit / MONTHLY_TARGET) * 100, 100) if total_profit > 0 else 0
    progress_bar = "▓" * int(progress_pct / 10) + "░" * (10 - int(progress_pct / 10))

    league_stats = {}
    for b in history:
        sport = b.get('sport', 'Inne')
        if sport not in league_stats:
            league_stats[sport] = {'wins': 0, 'total': 0, 'profit': 0}
        league_stats[sport]['total'] += 1
        league_stats[sport]['profit'] += b['profit']
        if b['win']: league_stats[sport]['wins'] += 1

    # --- RAPORT ---
    msg = f"📈 <b>STATYSTYKI DROGI DO 5000 PLN</b>\n"
    msg += f"━━━━━━━━━━━━━━━━━━\n"
    msg += f"💰 Zysk netto: <b>{total_profit:+.2f} PLN</b>\n"
    msg += f"📊 Yield: <b>{yield_val:.2f}%</b>\n"
    msg += f"🔄 Obrót: <b>{total_turnover:.0f} PLN</b>\n"
    msg += f"🏦 Kapitał: <b>{br_data['bankroll']:.2f} PLN</b>\n\n"

    msg += f"🎯 <b>CEL: 5 000 PLN / m-c</b>\n"
    msg += f"<code>[{progress_bar}]</code> {progress_pct:.1f}%\n"
    msg += f"━━━━━━━━━━━━━━━━━━\n\n"

    msg += f"🏆 <b>SKUTECZNOŚĆ DYSCYPLIN:</b>\n"
    sorted_leagues = sorted(league_stats.items(), key=lambda x: x[1]['profit'], reverse=True)
    for league, s in sorted_leagues:
        icon = "✅" if s['profit'] > 0 else "❌"
        msg += f"{icon} {league}: <b>{s['profit']:+.2f}</b>\n"

    msg += f"\n💡 <b>REKOMENDACJA:</b>\n"
    if yield_val > 5:
        msg += "• Strategia działa świetnie. Zwiększ obrót."
    elif yield_val > 0:
        msg += "• Zarabiasz, ale podatek Cię goni. Szukaj wyższych EV."
    else:
        msg += "• Uważaj! Obecnie dopłacasz do interesu. Sprawdź selekcję."

    send_telegram(msg)

if __name__ == "__main__":
    analyze_stats()
