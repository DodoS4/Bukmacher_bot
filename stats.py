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

# Mapa flag dla nowych i obecnych lig
FLAG_MAP = {
    "AUSTRIA": "🇦🇹", "DENMARK": "🇩🇰", "NORWAY": "🇳🇴", "SLOVAKIA": "🇸🇰",
    "SWEDEN": "🇸🇪", "FINLAND": "🇫🇮", "GERMANY": "🇩🇪", "CZECH": "🇨🇿",
    "SWITZERLAND": "🇨🇭", "POLAND": "🇵🇱", "SPAIN": "🇪🇸", "ITALY": "🇮🇹",
    "FRANCE": "🇫🇷", "PORTUGAL": "🇵🇹", "NETHERLANDS": "🇳🇱", "TURKEY": "🇹🇷",
    "BELGIUM": "🇧🇪", "GREECE": "🇬🇷", "SCOTLAND": "🏴󠁧󠁢󠁳󠁣󠁴󠁿", "UK": "🇬🇧", "USA": "🇺🇸"
}

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

    league_stats = {}
    total_net_profit = 0.0
    total_turnover = 0.0
    total_wins = 0
    valid_bets_count = 0

    for bet in history:
        # Całkowicie pomijamy remisy
        if bet.get('outcome') == 'Draw':
            continue

        valid_bets_count += 1
        profit = bet.get('profit', 0)
        total_net_profit += profit
        total_turnover += bet.get('stake', 250)
        
        if bet.get('status') == 'WIN':
            total_wins += 1

        # Identyfikacja sportu i czyszczenie nazwy ligi
        sport_raw = bet.get('sport', '')
        sport_icon = "🏒" if "icehockey" in sport_raw else "⚽" if "soccer" in sport_raw else "🎾"
        
        l_name = sport_raw.replace('soccer_', '').replace('icehockey_', '').replace('_', ' ').upper()
        
        # Dobieranie flagi na podstawie nazwy kraju w nazwie ligi
        flag = "🔹"
        for country, f_emoji in FLAG_MAP.items():
            if country in l_name:
                flag = f_emoji
                break
        
        full_league_display = f"{flag} {sport_icon} {l_name}"
        
        if full_league_display not in league_stats:
            league_stats[full_league_display] = {'profit': 0.0, 'bets': 0}
        league_stats[full_league_display]['profit'] += profit
        league_stats[full_league_display]['bets'] += 1
    
    if valid_bets_count == 0: return

    # --- RANKING LIG (TOP 5) ---
    sorted_leagues = sorted(league_stats.items(), key=lambda x: x[1]['profit'], reverse=True)
    ranking_str = ""
    for i, (name, data) in enumerate(sorted_leagues[:5]):
        ranking_str += f"{i+1}. {name}: <b>{data['profit']:+.2f}</b>\n"
    
    # --- ANALIZA OGÓLNA ---
    yield_val = (total_net_profit / total_turnover) * 100 if total_turnover > 0 else 0
    win_rate = (total_wins / valid_bets_count) * 100
    yield_emoji = "🟢" if yield_val > 5 else "🟡" if yield_val > 0 else "🔴"

    # --- PASEK POSTĘPU ---
    progress_pct = (total_net_profit / MONTHLY_TARGET) * 100
    bar_display = max(0, min(100, progress_pct))
    progress_bar = "🟢" * int(bar_display / 10) + "⚪" * (10 - int(bar_display / 10))

    # --- BUDOWANIE WIADOMOŚCI ---
    msg = f"📊 <b>RAPORT: STRATEGIA PRO ({valid_bets_count} TYPÓW)</b>\n"
    msg += f"━━━━━━━━━━━━━━━━━━\n"
    msg += f"💰 Zysk netto: <b>{total_net_profit:+.2f} PLN</b>\n"
    msg += f"{yield_emoji} Yield: <b>{yield_val:.2f}%</b> | WR: <b>{win_rate:.1f}%</b>\n"
    msg += f"🏦 Bankroll: <b>{br_data['bankroll']:.2f} PLN</b>\n"
    msg += f"━━━━━━━━━━━━━━━━━━\n"
    msg += f"🏆 <b>NAJLEPSZE RYNKI:</b>\n{ranking_str}\n"
    msg += f"━━━━━━━━━━━━━━━━━━\n"
    msg += f"🏁 <b>CEL: {MONTHLY_TARGET} PLN</b>\n"
    msg += f"<code>{progress_bar}</code> <b>{progress_pct:.1f}%</b>\n"
    msg += f"<i>System: 10 API Keys | Skanowanie 4x/dobę</i>"
    
    send_telegram(msg)

if __name__ == "__main__":
    analyze_stats()
