import json
import os
import requests
from datetime import datetime

# ================= KONFIGURACJA =================
HISTORY_FILE = "history.json"
BANKROLL_FILE = "bankroll.json"
TELEGRAM_TOKEN = os.getenv("T_TOKEN")
TELEGRAM_CHAT = os.getenv("T_CHAT_RESULTS") or os.getenv("T_CHAT")
MONTHLY_TARGET = 5000.0  # TWÓJ CEL

# Mapowanie ikon do raportu dyscyplin
ICONS = {
    "basketball_nba": "🏀", "icehockey_nhl": "🏒", "soccer_epl": "⚽",
    "soccer_spain_la_liga": "🇪🇸", "soccer_germany_bundesliga": "🇩🇪",
    "soccer_italy_serie_a": "🇮🇹", "soccer_france_ligue_one": "🇫🇷",
    "soccer_efl_championship": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "soccer_portugal_primeira_liga": "🇵🇹"
}

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
        print("Brak danych w history.json. Czekam na pierwsze rozliczone mecze.")
        return

    # --- OBLICZENIA GŁÓWNE ---
    total_profit = sum([b['profit'] for b in history])
    # Zmieniono domyślną stawkę na 250 PLN zgodnie z start.py
    total_turnover = sum([b.get('stake', 250) for b in history])
    
    # YIELD: (Zysk / Obrót) * 100
    yield_val = (total_profit / total_turnover) * 100 if total_turnover > 0 else 0
    
    # PROGRES DO 5000 PLN
    progress_pct = (total_profit / MONTHLY_TARGET) * 100 if total_profit > 0 else 0
    progress_pct_clamped = min(max(progress_pct, 0), 100)
    progress_bar = "▓" * int(progress_pct_clamped / 10) + "░" * (10 - int(progress_pct_clamped / 10))

    league_stats = {}
    for b in history:
        sport = b.get('sport', 'Inne')
        if sport not in league_stats:
            league_stats[sport] = {'wins': 0, 'total': 0, 'profit': 0}
        league_stats[sport]['total'] += 1
        league_stats[sport]['profit'] += b['profit']
        if b.get('win'): league_stats[sport]['wins'] += 1

    # --- KONSTRUKCJA RAPORTU ---
    msg = f"📈 <b>STATYSTYKI DROGI DO 5000 PLN</b>\n"
    msg += f"━━━━━━━━━━━━━━━━━━\n"
    msg += f"💰 Zysk netto: <b>{total_profit:+.2f} PLN</b>\n"
    msg += f"📊 Yield: <b>{yield_val:.2f}%</b>\n"
    msg += f"🔄 Obrót: <b>{total_turnover:.0f} PLN</b>\n"
    msg += f"🏦 Kapitał: <b>{br_data['bankroll']:.2f} PLN</b>\n\n"

    msg += f"🎯 <b>CEL: {MONTHLY_TARGET:.0f} PLN / m-c</b>\n"
    msg += f"<code>[{progress_bar}]</code> {progress_pct:.1f}%\n"
    msg += f"━━━━━━━━━━━━━━━━━━\n\n"

    msg += f"🏆 <b>SKUTECZNOŚĆ DYSCYPLIN:</b>\n"
    sorted_leagues = sorted(league_stats.items(), key=lambda x: x[1]['profit'], reverse=True)
    
    for league, s in sorted_leagues:
        emoji = ICONS.get(league, "🏆")
        msg += f"{emoji} {league.replace('soccer_', '').replace('_', ' ').title()}: <b>{s['profit']:+.2f}</b>\n"

    msg += f"\n💡 <b>REKOMENDACJA:</b>\n"
    if yield_val > 5:
        msg += "• Strategia działa świetnie. Rozważ stopniowe zwiększanie stawek."
    elif yield_val > 0:
        msg += "• Jesteś na plusie, ale podatek 12% zjada zyski. Szukaj wyższych kursów."
    else:
        msg += "• Uwaga: Drawdown. Trzymaj się planu i nie zwiększaj stawek emocjonalnie."

    send_telegram(msg)

if __name__ == "__main__":
    analyze_stats()
