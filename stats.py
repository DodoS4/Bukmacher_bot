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
    # 1. Wczytywanie plików
    history = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)
    
    coupons = []
    if os.path.exists(COUPONS_FILE):
        with open(COUPONS_FILE, "r", encoding="utf-8") as f:
            coupons = json.load(f)

    br_data = {"bankroll": 0.0}
    if os.path.exists(BANKROLL_FILE):
        with open(BANKROLL_FILE, "r", encoding="utf-8") as f:
            br_data = json.load(f)

    # 2. Liczenie oczekujących
    pending_count = len([c for c in coupons if not c.get('result')])
    
    now = datetime.now()
    next_24h = now + timedelta(hours=24)
    upcoming_24h_count = 0
    
    for c in coupons:
        if 'start_time' in c:
            try:
                st_str = c['start_time'].replace('Z', '+00:00')
                match_time = datetime.fromisoformat(st_str).replace(tzinfo=None)
                if now <= match_time <= next_24h:
                    upcoming_24h_count += 1
            except: continue

    # 3. Analiza historii
    league_stats = {}
    total_net_profit = 0.0
    total_turnover = 0.0
    total_wins = 0
    valid_bets_count = 0

    for bet in history:
        if bet.get('outcome') == 'Draw' and bet.get('status') == 'VOID':
            continue

        valid_bets_count += 1
        profit = bet.get('profit', 0)
        total_net_profit += profit
        total_turnover += bet.get('stake', 250)
        
        if bet.get('status') == 'WIN':
            total_wins += 1

        sport_raw = bet.get('sport', '').lower()
        s_icon = "🏒" if "icehockey" in sport_raw else "⚽" if "soccer" in sport_raw else "🏀" if "basketball" in sport_raw else "🎾" if "tennis" in sport_raw else "🔹"
        l_name_clean = sport_raw.replace('soccer_', '').replace('icehockey_', '').replace('basketball_', '').replace('tennis_', '').replace('_', ' ').upper()
        
        flag = "🏳️"
        for country, f_emoji in FLAG_MAP.items():
            if country in l_name_clean:
                flag = f_emoji
                break
        
        full_display = f"{s_icon} {flag} {l_name_clean}"
        if full_display not in league_stats:
            league_stats[full_display] = {'profit': 0.0}
        league_stats[full_display]['profit'] += profit
    
    # 4. Obliczenia
    yield_val = (total_net_profit / total_turnover * 100) if total_turnover > 0 else 0
    win_rate = (total_wins / valid_bets_count * 100) if valid_bets_count > 0 else 0
    progress_pct = (total_net_profit / MONTHLY_TARGET * 100)

    # 5. Zapis dla WWW
    web_data = {
        "total_profit": round(total_net_profit, 2),
        "yield": round(yield_val, 2),
        "pending_count": pending_count,
        "upcoming_24h": upcoming_24h_count,
        "win_rate": round(win_rate, 1),
        "bankroll": round(br_data.get('bankroll', 0), 2),
        "last_update": datetime.now().strftime("%H:%M")
    }
    with open(WEB_STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(web_data, f, indent=4)

    # 6. Telegram
    bar_len = int(max(0, min(100, progress_pct)) / 10)
    progress_bar = "🟢" * bar_len + "⚪" * (10 - bar_len)

    msg = f"🚀 <b>STATUS TYPERA: DAWID</b> 🚀\n"
    msg += f"📅 <code>Aktualizacja: {datetime.now().strftime('%d.%m %H:%M')}</code>\n\n"
    msg += f"💰 <b>WYNIKI:</b>\n"
    msg += f"┣ Zysk netto: <b>{total_net_profit:+.2f} PLN</b>\n"
    msg += f"┗ Yield: <b>{yield_val:.2f}%</b>\n\n"
    msg += f"⏳ <b>W GRZE: {pending_count} kuponów</b>\n"
    msg += f"📅 <b>NASTĘPNE 24H: {upcoming_24h_count} meczów</b>\n\n"
    msg += f"🏆 <b>TOP LIGI:</b>\n"
    
    sorted_leagues = sorted(league_stats.items(), key=lambda x: x[1]['profit'], reverse=True)
    for i, (name, data) in enumerate(sorted_leagues[:3]):
        icon = ["🥇", "🥈", "🥉"][i]
        msg += f"{icon} {name}: <b>{data['profit']:+.2f}</b>\n"

    msg += f"\n🏁 <b>CEL: {MONTHLY_TARGET} PLN</b>\n"
    msg += f"<code>{progress_bar}</code> <b>{progress_pct:.1f}%</b>"
    
    send_telegram(msg)

if __name__ == "__main__":
    analyze_stats()
