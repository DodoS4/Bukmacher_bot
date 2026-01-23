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

# Mapa flag dla krajów występujących w nazwach lig
FLAG_MAP = {
    "AUSTRIA": "🇦🇹", "DENMARK": "🇩🇰", "NORWAY": "🇳🇴", "SLOVAKIA": "🇸🇰",
    "SWEDEN": "🇸🇪", "FINLAND": "🇫🇮", "GERMANY": "🇩🇪", "CZECH": "🇨🇿",
    "SWITZERLAND": "🇨🇭", "POLAND": "🇵🇱", "SPAIN": "🇪🇸", "ITALY": "🇮🇹",
    "FRANCE": "🇫🇷", "PORTUGAL": "🇵🇹", "NETHERLANDS": "🇳🇱", "TURKEY": "🇹🇷",
    "BELGIUM": "🇧🇪", "GREECE": "🇬🇷", "SCOTLAND": "🏴󠁧󠁢󠁳󠁣󠁴󠁿", "UK": "🇬🇧", 
    "USA": "🇺🇸", "NHL": "🇺🇸", "EPL": "🏴󠁧󠁢󠁥󠁮󠁧󠁿"
}

def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT, "text": message, "parse_mode": "HTML"}, timeout=10)
    except: pass

def analyze_stats():
    print(f"📊 GENEROWANIE RAPORTU: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if not os.path.exists(HISTORY_FILE): 
        print("Brak historii do analizy.")
        return
    
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)
    except: return
    
    br_data = {"bankroll": 0.0}
    if os.path.exists(BANKROLL_FILE):
        try:
            with open(BANKROLL_FILE, "r", encoding="utf-8") as f:
                br_data = json.load(f)
        except: pass
    
    if not history: return

    league_stats = {}
    total_net_profit = 0.0
    total_turnover = 0.0
    total_wins = 0
    valid_bets_count = 0

    for bet in history:
        # ROZWIĄZANIE: Analizujemy tylko mecze ze statusem WIN lub LOSS
        if bet.get('status') not in ['WIN', 'LOSS']:
            continue

        valid_bets_count += 1
        profit = float(bet.get('profit', 0))
        stake = float(bet.get('stake', 250))
        
        total_net_profit += profit
        total_turnover += stake
        
        if bet.get('status') == 'WIN':
            total_wins += 1

        # --- LOGIKA IKON SPORTOWYCH ---
        sport_raw = bet.get('sport', '').lower()
        s_icon = "🏒" if "icehockey" in sport_raw else "⚽" if "soccer" in sport_raw else "🏀" if "basketball" in sport_raw else "🎾" if "tennis" in sport_raw else "🔹"

        # Czyszczenie nazwy ligi do wyświetlania
        l_name_clean = sport_raw.replace('soccer_', '').replace('icehockey_', '').replace('basketball_', '').replace('tennis_', '').replace('_', ' ').upper()
        
        # Dobieranie flagi
        flag = "🏳️"
        for country, f_emoji in FLAG_MAP.items():
            if country in l_name_clean:
                flag = f_emoji
                break
        
        full_display = f"{s_icon} {flag} {l_name_clean}"
        
        if full_display not in league_stats:
            league_stats[full_display] = {'profit': 0.0, 'bets': 0}
        league_stats[full_display]['profit'] += profit
        league_stats[full_display]['bets'] += 1
    
    if valid_bets_count == 0:
        print("Brak rozliczonych typów do raportu.")
        return

    # --- RANKING LIG (TOP 5) ---
    sorted_leagues = sorted(league_stats.items(), key=lambda x: x[1]['profit'], reverse=True)
    ranking_str = ""
    for i, (name, data) in enumerate(sorted_leagues[:5]):
        ranking_str += f"{i+1}. {name}: <b>{data['profit']:+.2f}</b> ({data['bets']} typów)\n"
    
    # --- ANALIZA OGÓLNA ---
    yield_val = (total_net_profit / total_turnover) * 100 if total_turnover > 0 else 0
    win_rate = (total_wins / valid_bets_count) * 100
    yield_emoji = "🟢" if yield_val > 5 else "🟡" if yield_val > 0 else "🔴"

    # --- PASEK POSTĘPU ---
    # Zabezpieczenie przed ujemnym zyskiem w pasku
    progress_pct = (total_net_profit / MONTHLY_TARGET) * 100
    safe_progress = max(0, min(100, progress_pct))
    bar_len = int(safe_progress / 10)
    progress_bar = "🟢" * bar_len + "⚪" * (10 - bar_len)

    # --- WIADOMOŚĆ ---
    msg = (f"📊 <b>RAPORT ANALITYCZNY ({valid_bets_count} TYPÓW)</b>\n"
           f"━━━━━━━━━━━━━━━━━━\n"
           f"💰 Zysk netto: <b>{total_net_profit:+.2f} PLN</b>\n"
           f"{yield_emoji} Yield: <b>{yield_val:.2f}%</b> | WR: <b>{win_rate:.1f}%</b>\n"
           f"🏦 Bankroll: <b>{br_data['bankroll']:.2f} PLN</b>\n"
           f"━━━━━━━━━━━━━━━━━━\n"
           f"🏆 <b>LIDERZY RYNKU:</b>\n{ranking_str}\n"
           f"━━━━━━━━━━━━━━━━━━\n"
           f"🏁 <b>CEL: {MONTHLY_TARGET} PLN</b>\n"
           f"<code>{progress_bar}</code> <b>{progress_pct:.1f}%</b>\n"
           f"<i>Rozliczanie uwzględnia podatek 12%</i>")
    
    send_telegram(msg)
    print("✅ Raport wysłany na Telegram.")

if __name__ == "__main__":
    analyze_stats()
