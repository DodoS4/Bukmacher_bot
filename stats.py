import json
import os
import requests
from datetime import datetime, timedelta, timezone

def get_env_safe(name):
    val = os.environ.get(name) or os.getenv(name)
    return str(val).strip() if val and len(str(val).strip()) > 0 else None

TOKEN = get_env_safe("T_TOKEN")
CHAT_TARGET = get_env_safe("T_CHAT_RESULTS") or get_env_safe("T_CHAT")
STARTING_BANKROLL = 5000.0

def generate_stats():
    if not os.path.exists('history.json'): return False, "❌ Brak danych."
    try:
        with open('history.json', 'r', encoding='utf-8') as f:
            history = json.load(f)
    except: return False, "❌ Błąd pliku."

    total_profit, profit_24h = 0.0, 0.0
    wins, losses, turnover = 0, 0, 0.0
    series_icons = []
    match_list = []
    stats_by_sport = {}
    chart_data = [] # Dane do wykresu na WWW
    
    current_balance = STARTING_BANKROLL
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)

    for bet in history:
        prof = float(bet.get('profit', 0))
        stk = float(bet.get('stake', 0))
        sport = bet.get('sport', 'other')
        
        # Agregacja per sport
        sport_type = "🏒 Hokej" if "icehockey" in sport else ("⚽ Piłka" if "soccer" in sport else "🏀 Inne")
        if sport_type not in stats_by_sport:
            stats_by_sport[sport_type] = {"profit": 0.0, "count": 0}
        stats_by_sport[sport_type]["profit"] += prof
        stats_by_sport[sport_type]["count"] += 1

        total_profit += prof
        turnover += stk
        current_balance += prof
        icon = "✅" if prof > 0 else ("❌" if prof < 0 else "⚠️")
        
        if prof > 0: wins += 1
        elif prof < 0: losses += 1
        series_icons.append(icon)

        # Dane do wykresu progresji
        chart_data.append(round(total_profit, 2))

        b_time = bet.get('time') or bet.get('date')
        if b_time:
            try:
                dt_obj = datetime.fromisoformat(b_time.replace("Z", "+00:00"))
                if dt_obj > yesterday: profit_24h += prof
            except: pass

        match_list.append(f"{icon} {bet.get('home')} - {bet.get('away')} | <b>{bet.get('score', '?-?')}</b> | <code>{prof:+.2f}</code>")

    total_bets = len(series_icons)
    win_rate = round((wins/total_bets*100) if total_bets > 0 else 0, 1)
    yield_val = round((total_profit/turnover*100) if turnover > 0 else 0, 2)
    roi_val = round((total_profit / STARTING_BANKROLL * 100), 2)

    # --- NOWOŚĆ: ZAPIS DO STATS.JSON DLA WWW ---
    web_stats = {
        "zysk_total": round(total_profit, 2),
        "zysk_24h": round(profit_24h, 2),
        "skutecznosc": win_rate,
        "yield": yield_val,
        "roi": roi_val,
        "obrot": round(turnover, 2),
        "bankroll": round(STARTING_BANKROLL + total_profit, 2),
        "wykres": chart_data,
        "seria": series_icons[-15:],
        "last_sync": datetime.now().strftime("%H:%M:%S"),
        "stats_by_sport": stats_by_sport
    }
    
    with open('stats.json', 'w', encoding='utf-8') as f:
        json.dump(web_stats, f, indent=4)

    # --- RAPORT TELEGRAM ---
    report = [
        "📊 <b>DASHBOARD STATYSTYK</b>",
        f"━━━━━━━━━━━━━━━",
        f"🏦 <b>BANKROLL:</b> <code>{(STARTING_BANKROLL + total_profit):.2f} PLN</code>",
        f"💰 Zysk Total: <b>{total_profit:.2f} PLN</b>",
        f"📅 Ostatnie 24h: <b>{profit_24h:+.2f} PLN</b>",
        f"🎯 Skuteczność: <b>{win_rate}%</b>",
        f"📈 Yield: <b>{yield_val}%</b>",
        f"━━━━━━━━━━━━━━━",
        "🏆 <b>ZYSKI PER DYSCYPLINA:</b>"
    ]
    
    for s_name, s_data in stats_by_sport.items():
        report.append(f"{s_name}: <b>{s_data['profit']:+.2f} PLN</b> ({s_data['count']} typów)")

    report.extend(["", "📝 <b>OSTATNIE WYNIKI:</b>"])
    report.extend(match_list[-10:])
    report.append(f"━━━━━━━━━━━━━━━\n🔥 <b>Seria:</b> {''.join(series_icons[-15:])}")

    return True, "\n".join(report)

if __name__ == "__main__":
    success, text = generate_stats()
    if success and TOKEN and CHAT_TARGET:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                      json={"chat_id": CHAT_TARGET, "text": text, "parse_mode": "HTML"})
