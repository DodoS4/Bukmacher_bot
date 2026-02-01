import json
import os
import requests
from datetime import datetime, timedelta, timezone

TOKEN = os.getenv("T_TOKEN")
CHAT_ID = os.getenv("T_CHAT_RESULTS")
STARTING_BANKROLL = 5000.0

def generate_stats():
    filename = 'history.json'
    if not os.path.exists(filename): return

    try:
        with open(filename, 'r', encoding='utf-8') as f:
            history = json.load(f)
        if isinstance(history, str): history = json.loads(history)
    except: return

    if not isinstance(history, list) or not history: return

    # Obliczenia
    total_profit = sum(float(b.get('profit', 0)) for b in history if isinstance(b, dict))
    total_stk = sum(float(b.get('stake', 0)) for b in history if isinstance(b, dict))
    wins = sum(1 for b in history if isinstance(b, dict) and float(b.get('profit', 0)) > 0)
    
    # Progresja do wykresu Chart.js
    current_p = 0
    chart_data = [0]
    sorted_history = sorted(history, key=lambda x: x.get('time', ''))
    for b in sorted_history:
        current_p += float(b.get('profit', 0))
        chart_data.append(round(current_p, 2))

    now = datetime.now(timezone.utc)
    p_24h = sum(float(b.get('profit', 0)) for b in history 
                if isinstance(b, dict) and datetime.fromisoformat(b.get('time', '').replace("Z", "+00:00")) > (now - timedelta(days=1)))

    # --- GENEROWANIE STATS.JSON DLA WWW ---
    web_data = {
        "zysk_total": round(total_profit, 2),
        "zysk_24h": round(p_24h, 2),
        "roi": round((total_profit / STARTING_BANKROLL * 100), 2),
        "obrot": round(total_stk, 2),
        "yield": round((total_profit / total_stk * 100), 2) if total_stk > 0 else 0,
        "total_bets_count": len(history),
        "skutecznosc": round((wins/len(history)*100), 1) if history else 0,
        "wykres": chart_data,
        "last_sync": datetime.now().strftime("%H:%M:%S")
    }

    with open('stats.json', 'w', encoding='utf-8') as f:
        json.dump(web_data, f, indent=4)
    print("✅ Plik stats.json zaktualizowany pod HTML.")

    # --- RAPORT TELEGRAM ---
    res_list = []
    for b in history[-10:]:
        if not isinstance(b, dict): continue
        icon = "✅" if float(b.get('profit', 0)) > 0 else "❌"
        res_list.append(f"{icon} {b.get('home')} - {b.get('away')} | {b.get('score', '0:0')} | {float(b.get('profit', 0)):+.2f}")

    report = [
        "📊 <b>STATYSTYKI</b>", "━━━━━━━━━━━━━━━",
        f"🏦 <b>BANKROLL:</b> <code>{STARTING_BANKROLL + total_profit:.2f} PLN</code>",
        f"💰 <b>Zysk Total:</b> <code>{total_profit:.2f} PLN</code>",
        f"📅 <b>Ostatnie 24h:</b> <code>{p_24h:+.2f} PLN</code>",
        f"🎯 <b>Skuteczność:</b> <code>{web_data['skutecznosc']}%</code>",
        f"📈 <b>Yield:</b> <code>{web_data['yield']}%</code>",
        "━━━━━━━━━━━━━━━", "📝 <b>OSTATNIE WYNIKI:</b>",
        "\n".join(res_list), "━━━━━━━━━━━━━━━"
    ]

    if TOKEN and CHAT_ID:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                     json={"chat_id": CHAT_ID, "text": "\n".join(report), "parse_mode": "HTML"})

if __name__ == "__main__": generate_stats()
