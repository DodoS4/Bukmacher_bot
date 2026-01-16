import json
import os
import requests

# ================= KONFIGURACJA =================
HISTORY_FILE = "history.json"
BANKROLL_FILE = "bankroll.json"
TELEGRAM_TOKEN = os.getenv("T_TOKEN")
TELEGRAM_CHAT = os.getenv("T_CHAT_RESULTS") or os.getenv("T_CHAT")
MONTHLY_TARGET = 5000.0

# Mapowanie ikon dla czytelności raportu
ICONS = {
    "NBA": "🏀", "NHL": "🏒", "EPL": "⚽",
    "SPAIN LA LIGA": "🇪🇸", "GERMANY BUNDESLIGA": "🇩🇪",
    "ITALY SERIE A": "🇮🇹", "FRANCE LIGUE ONE": "🇫🇷",
    "EFL CHAMPIONSHIP": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "PORTUGAL PRIMEIRA LIGA": "🇵🇹"
}

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

    total_profit = sum([b['profit'] for b in history])
    total_turnover = sum([b.get('stake', 250) for b in history])
    yield_val = (total_profit / total_turnover) * 100 if total_turnover > 0 else 0
    
    # Obliczanie paska postępu
    progress_pct = (total_profit / MONTHLY_TARGET) * 100
    progress_bar = "▓" * int(min(max(progress_pct, 0), 100) / 10) + "░" * (10 - int(min(max(progress_pct, 0), 100) / 10))

    league_stats = {}
    for b in history:
        # Standaryzacja nazwy ligi do formatu ICONS
        raw_sport = b.get('sport', 'INNE')
        sport = raw_sport.replace("soccer_", "").replace("_", " ").upper()
        
        if sport not in league_stats:
            league_stats[sport] = {'profit': 0}
        league_stats[sport]['profit'] += b['profit']

    # --- BUDOWANIE WIADOMOŚCI ---
    msg = f"📈 <b>STATYSTYKI DROGI DO 5000 PLN</b>\n"
    msg += f"━━━━━━━━━━━━━━━━━━\n"
    msg += f"💰 Zysk netto: <b>{total_profit:+.2f} PLN</b>\n"
    msg += f"📊 Yield: <b>{yield_val:.2f}%</b>\n"
    msg += f"🏦 Kapitał: <b>{br_data['bankroll']:.2f} PLN</b>\n\n"

    msg += f"🎯 <b>CEL: {MONTHLY_TARGET:.0f} PLN</b>\n"
    msg += f"<code>[{progress_bar}]</code> {max(progress_pct, 0):.1f}%\n"
    msg += f"━━━━━━━━━━━━━━━━━━\n\n"

    msg += f"🏆 <b>SKUTECZNOŚĆ DYSCYPLIN:</b>\n"
    sorted_leagues = sorted(league_stats.items(), key=lambda x: x[1]['profit'], reverse=True)
    for league, s in sorted_leagues:
        emoji = ICONS.get(league, "🏆")
        msg += f"{emoji} {league}: <b>{s['profit']:+.2f}</b>\n"

    send_telegram(msg)

if __name__ == "__main__":
    analyze_stats()
