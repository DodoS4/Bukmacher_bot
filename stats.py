import json
import os
import requests
from datetime import datetime, timedelta

# ================= KONFIGURACJA =================
HISTORY_FILE = "history.json"
BANKROLL_FILE = "bankroll.json"
COUPONS_FILE = "coupons.json"
WEB_STATS_FILE = "web_stats.json"
TELEGRAM_TOKEN = os.getenv("T_TOKEN")
TELEGRAM_CHAT = os.getenv("T_CHAT_RESULTS") or os.getenv("T_CHAT")
MONTHLY_TARGET = 5000.0

FLAG_MAP = {
    "AUSTRIA": "🇦🇹", "DENMARK": "🇩🇰", "NORWAY": "🇳🇴", "SLOVAKIA": "🇸🇰",
    "SWEDEN": "🇸🇪", "FINLAND": "🇫🇮", "GERMANY": "🇩🇪", "CZECH": "🇨🇿",
    "SWITZERLAND": "🇨🇭", "POLAND": "🇵🇱", "SPAIN": "🇪🇸", "ITALY": "🇮🇹",
    "FRANCE": "🇫🇷", "PORTUGAL": "🇵🇹", "NETHERLANDS": "🇳🇱", "TURKEY": "🇹🇷",
    "BELGIUM": "🇧🇪", "GREECE": "🇬🇷", "SCOTLAND": "🏴󠁧󠁢󠁳󠁣󠁴󠁿", "UK": "🇬🇧", 
    "USA": "🇺🇸", "NHL": "🇺🇸", "EPL": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "NBA": "🇺🇸"
}

def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT, "text": message, "parse_mode": "HTML"})
    except: pass

def analyze_stats():
    # 1. Wczytywanie plików (Z poprawką kodowania)
    history = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            try:
                history = json.load(f)
            except: history = []
    
    coupons = []
    if os.path.exists(COUPONS_FILE):
        with open(COUPONS_FILE, "r", encoding="utf-8") as f:
            try:
                coupons = json.load(f)
            except: coupons = []

    # 2. Liczenie oczekujących (z kuponów)
    pending_count = len([c for c in coupons if not c.get('result')])
    
    # 3. Analiza historii (Całkowita i spójna ze stroną WWW)
    league_stats = {}
    total_net_profit = 0.0
    total_turnover = 0.0
    total_wins = 0
    valid_bets_count = 0

    for bet in history:
        # Pomiń tylko jeśli to zwrot (Draw/VOID), ale licz wszystko co ma zysk/stratę
        profit = float(bet.get('profit', 0))
        stake = float(bet.get('stake', 250))
        
        # Jeśli mecz jest rozliczony (ma profit różny od 0 lub status WIN/LOSS)
        valid_bets_count += 1
        total_net_profit += profit
        total_turnover += stake
        
        if profit > 0 or bet.get('status') == 'WIN':
            total_wins += 1

        # Generowanie ikony i nazwy ligi
        sport_raw = bet.get('sport', '').lower()
        s_icon = "🏒" if "icehockey" in sport_raw else "⚽" if "soccer" in sport_raw else "🏀" if "basketball" in sport_raw else "🎾" if "tennis" in sport_raw else "🔹"
        
        # Bardziej agresywne czyszczenie nazwy ligi
        l_name_clean = sport_raw.replace('soccer_', '').replace('icehockey_', '').replace('basketball_', '').replace('tennis_', '').replace('_', ' ').upper()
        
        flag = "🏳️"
        for country, f_emoji in FLAG_MAP.items():
            if country in l_name_clean or country in sport_raw.upper():
                flag = f_emoji
                break
        
        league_key = f"{s_icon} {flag} {l_name_clean}"
        if league_key not in league_stats:
            league_stats[league_key] = {'profit': 0.0}
        league_stats[league_key]['profit'] += profit
    
    # 4. Obliczenia końcowe
    yield_val = (total_net_profit / total_turnover * 100) if total_turnover > 0 else 0
    progress_pct = (total_net_profit / MONTHLY_TARGET * 100)

    # 5. Telegram - Generowanie wiadomości
    bar_len = int(max(0, min(100, progress_pct)) / 10)
    progress_bar = "🟢" * bar_len + "⚪" * (10 - bar_len)

    msg = f"🚀 <b>STATUS TYPERA: DAWID</b> 🚀\n"
    msg += f"📅 <code>Aktualizacja: {datetime.now().strftime('%d.%m %H:%M')}</code>\n\n"
    msg += f"💰 <b>WYNIKI CAŁKOWITE:</b>\n" # Zmienione na TOTAL
    msg += f"┣ Zysk netto: <b>{total_net_profit:+.2f} PLN</b>\n"
    msg += f"┗ Yield: <b>{yield_val:.2f}%</b>\n\n"
    msg += f"⏳ <b>W GRZE: {pending_count} kuponów</b>\n\n"
    
    msg += f"🏆 <b>TOP LIGI (ALL-TIME):</b>\n"
    
    # Sortowanie lig po zysku
    sorted_leagues = sorted(league_stats.items(), key=lambda x: x[1]['profit'], reverse=True)
    for i, (name, data) in enumerate(sorted_leagues[:3]):
        icon = ["🥇", "🥈", "🥉"][i]
        msg += f"{icon} {name}: <b>{data['profit']:+.2f}</b>\n"

    msg += f"\n🏁 <b>CEL: {MONTHLY_TARGET} PLN</b>\n"
    msg += f"<code>{progress_bar}</code> <b>{progress_pct:.1f}%</b>"
    
    send_telegram(msg)
    print(f"✅ Statystyki wysłane. Zysk: {total_net_profit}")

if __name__ == "__main__":
    analyze_stats()
