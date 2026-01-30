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

    total_profit, turnover = 0.0, 0.0
    wins, losses = 0, 0
    league_map = {}
    chart_data = []

    for bet in history:
        prof = float(bet.get('profit', 0))
        stk = float(bet.get('stake', 0))
        # Normalizacja nazwy ligi
        raw_league = bet.get('sport', 'INNE').upper().replace('SOCCER_', '').replace('ICEHOCKEY_', '').replace('_', ' ')
        
        total_profit += prof
        turnover += stk
        chart_data.append(round(total_profit, 2))
        
        if prof > 0: wins += 1
        elif prof < 0: losses += 1

        if raw_league not in league_map:
            league_map[raw_league] = {'profit': 0.0, 'bets': 0}
        league_map[raw_league]['profit'] += prof
        league_map[raw_league]['bets'] += 1

    # Sortowanie lig
    sorted_leagues = sorted(league_map.items(), key=lambda x: x[1]['profit'], reverse=True)
    
    top_leagues = sorted_leagues[:3]
    bottom_leagues = sorted_leagues[-3:]

    win_rate = round((wins/len(history)*100) if len(history) > 0 else 0, 1)
    yield_val = round((total_profit/turnover*100) if turnover > 0 else 0, 2)

    # Zapis do stats.json
    web_stats = {
        "zysk_total": round(total_profit, 2),
        "skutecznosc": win_rate,
        "yield": yield_val,
        "obrot": round(turnover, 2),
        "total_bets_count": len(history),
        "wykres": chart_data,
        "last_sync": datetime.now().strftime("%H:%M:%S")
    }
    
    with open('stats.json', 'w', encoding='utf-8') as f:
        json.dump(web_stats, f, indent=4)

    # Budowanie raportu na Telegram
    msg = [
        "📊 <b>RAPORT ANALITYCZNY LIG</b>",
        f"━━━━━━━━━━━━━━━",
        f"💰 Zysk: <b>{total_profit:.2f} PLN</b>",
        f"📈 Yield: <b>{yield_val}%</b>",
        f"━━━━━━━━━━━━━━━",
        "✅ <b>NAJLEPSZE LIGI:</b>"
    ]
    
    for name, data in top_leagues:
        if data['profit'] > 0:
            msg.append(f"• {name}: <b>+{data['profit']:.2f}</b> ({data['bets']} typów)")

    msg.append("\n❌ <b>NAJSŁABSZE LIGI:</b>")
    for name, data in bottom_leagues:
        if data['profit'] < 0:
            msg.append(f"• {name}: <b>{data['profit']:.2f}</b> ({data['bets']} typów)")

    msg.append(f"━━━━━━━━━━━━━━━")
    return True, "\n".join(msg)

if __name__ == "__main__":
    success, text = generate_stats()
    if success and TOKEN and CHAT_TARGET:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", json={"chat_id": CHAT_TARGET, "text": text, "parse_mode": "HTML"})
