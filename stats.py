import json
import os
import requests
from datetime import datetime, timedelta, timezone

# ================= ODCZYT Z SECRETS =================
TOKEN = os.getenv("T_TOKEN")
CHAT_ID = os.getenv("T_CHAT_RESULTS") # Tutaj idą statystyki
STARTING_BANKROLL = 5000.0

def generate_stats():
    if not os.path.exists('history.json'): return
    with open('history.json', 'r', encoding='utf-8') as f:
        history = json.load(f)
    
    if not history: return

    total_profit = sum(float(b.get('profit', 0)) for b in history)
    total_stk = sum(float(b.get('stake', 0)) for b in history)
    wins = sum(1 for b in history if float(b.get('profit', 0)) > 0)
    
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)
    profit_24h = sum(float(b.get('profit', 0)) for b in history 
                    if datetime.fromisoformat(b.get('time', '').replace("Z", "+00:00")) > yesterday)

    # Formatowanie listy ostatnich 10 wyników
    results_list = []
    for bet in history[-10:]:
        icon = "✅" if float(bet.get('profit', 0)) > 0 else "❌"
        res = f"{icon} {bet.get('home')} - {bet.get('away')} | {bet.get('score', '0:0')} | {float(bet.get('profit', 0)):+.2f}"
        results_list.append(res)

    report = [
        "📊 <b>STATYSTYKI</b>",
        "━━━━━━━━━━━━━━━",
        f"🏦 <b>BANKROLL:</b> <code>{STARTING_BANKROLL + total_profit:.2f} PLN</code>",
        f"💰 <b>Zysk Total:</b> <code>{total_profit:.2f} PLN</code>",
        f"📅 <b>Ostatnie 24h:</b> <code>{profit_24h:+.2f} PLN</code>",
        f"🎯 <b>Skuteczność:</b> <code>{(wins/len(history)*100):.1f}%</code>",
        f"📈 <b>Yield:</b> <code>{(total_profit/total_stk*100) if total_stk > 0 else 0:.2f}%</code>",
        "━━━━━━━━━━━━━━━",
        "📝 <b>OSTATNIE WYNIKI:</b>",
        "\n".join(results_list),
        "━━━━━━━━━━━━━━━"
    ]

    if TOKEN and CHAT_ID:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                     json={"chat_id": CHAT_ID, "text": "\n".join(report), "parse_mode": "HTML"})

if __name__ == "__main__":
    generate_stats()
