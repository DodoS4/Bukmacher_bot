import json, os, requests
from datetime import datetime, timedelta, timezone

TOKEN = os.getenv("T_TOKEN")
CHAT_STATS = os.getenv("T_CHAT_RESULTS")
STARTING_BANKROLL = 5000.0

def generate_stats():
    if not os.path.exists('history.json'): return False, "Brak history.json"
        
    try:
        with open('history.json', 'r', encoding='utf-8') as f:
            history = json.load(f)
    except: return False, "Błąd JSON"

    total_profit, total_turnover, profit_24h = 0.0, 0.0, 0.0
    wins, losses = 0, 0
    series_icons, chart_data = [], [0]
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)

    # Sortujemy historię datami, aby wykres rósł chronologicznie
    history.sort(key=lambda x: x.get('time', ''))

    current_p = 0
    for bet in history:
        prof = float(bet.get('profit', 0))
        stk = float(bet.get('stake', 0))
        total_profit += prof
        total_turnover += stk
        
        current_p += prof
        chart_data.append(round(current_p, 2))

        icon = "✅" if prof > 0 else "❌"
        if prof > 0: wins += 1
        else: losses += 1
        series_icons.append(icon)

        try:
            b_time = datetime.fromisoformat(bet.get('time').replace("Z", "+00:00"))
            if b_time > yesterday: profit_24h += prof
        except: pass

    total_bets = wins + losses
    win_rate = (wins / total_bets * 100) if total_bets > 0 else 0
    yield_val = (total_profit / total_turnover * 100) if total_turnover > 0 else 0

    # KLUCZE DOPASOWANE DO TWOJEGO HTML
    web_data = {
        "zysk_total": round(total_profit, 2),
        "zysk_24h": round(profit_24h, 2),
        "yield": round(yield_val, 1),
        "roi": round((total_profit / STARTING_BANKROLL * 100), 1),
        "obrot": round(total_turnover, 2),
        "skutecznosc": round(win_rate, 1),
        "total_bets_count": total_bets,
        "wykres": chart_data,
        "last_sync": now.strftime("%H:%M:%S")
    }

    with open('stats.json', 'w', encoding='utf-8') as f:
        json.dump(web_data, f, indent=4)

    report = [
        "📊 *DASHBOARD STATYSTYK*",
        f"💰 *Zysk Total:* `{total_profit:.2f} PLN`",
        f"🎯 *Skuteczność:* `{win_rate:.1f}%`",
        f"📈 *Yield:* `{yield_val:.2f}%`",
        f"🔥 *Ostatnie:* {''.join(series_icons[-10:])}"
    ]
    return True, "\n".join(report)

if __name__ == "__main__":
    success, text = generate_stats()
    if success and TOKEN and CHAT_STATS:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                     json={"chat_id": CHAT_STATS, "text": text, "parse_mode": "Markdown"})
