import json, os, requests
from datetime import datetime, timedelta, timezone

TOKEN = os.getenv("T_TOKEN")
CHAT_STATS = os.getenv("T_CHAT_RESULTS") # Upewnij się, że masz ten SECRET w GitHub
STARTING_BANKROLL = 5000.0

def generate_stats():
    if not os.path.exists('history.json'): return False, "Brak history.json"
        
    try:
        with open('history.json', 'r', encoding='utf-8') as f:
            history = json.load(f)
        if isinstance(history, str): history = json.loads(history)
    except: return False, "Błąd odczytu bazy danych"

    total_profit, total_turnover, profit_24h = 0.0, 0.0, 0.0
    wins = 0
    chart_data = [0]
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)

    # Sortowanie chronologiczne dla poprawnego wykresu
    history.sort(key=lambda x: x.get('time', ''))

    current_p = 0
    for bet in history:
        prof = float(bet.get('profit', 0))
        stk = float(bet.get('stake', 0))
        total_profit += prof
        total_turnover += stk
        
        current_p += prof
        chart_data.append(round(current_p, 2))

        if prof > 0: wins += 1

        try:
            b_time = datetime.fromisoformat(bet.get('time').replace("Z", "+00:00"))
            if b_time > yesterday: profit_24h += prof
        except: pass

    total_bets = len(history)
    win_rate = (wins / total_bets * 100) if total_bets > 0 else 0
    yield_val = (total_profit / total_turnover * 100) if total_turnover > 0 else 0

    # KLUCZE DOPASOWANE DO TWOJEGO index.html
    web_data = {
        "zysk_total": round(total_profit, 2),
        "zysk_24h": round(profit_24h, 2),
        "yield": round(yield_val, 2),
        "roi": round((total_profit / STARTING_BANKROLL * 100), 2),
        "obrot": round(total_turnover, 2),
        "skutecznosc": round(win_rate, 1),
        "total_bets_count": total_bets,
        "wykres": chart_data,
        "last_sync": datetime.now().strftime("%H:%M:%S")
    }

    with open('stats.json', 'w', encoding='utf-8') as f:
        json.dump(web_data, f, indent=4)
    
    return True, "✅ Statystyki zsynchronizowane z WWW"

if __name__ == "__main__":
    success, msg = generate_stats()
    print(msg)
