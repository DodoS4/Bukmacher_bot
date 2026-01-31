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
    # Pobieranie historii
    if not os.path.exists('history.json'): return False, "❌ Brak danych."
    try:
        with open('history.json', 'r', encoding='utf-8') as f:
            history = json.load(f)
    except: return False, "❌ Błąd pliku."

    # Pobieranie aktywnych kuponów (aby wyczyścić UNDEFINED na stronie)
    active_coupons = []
    if os.path.exists('coupons.json'):
        try:
            with open('coupons.json', 'r', encoding='utf-8') as f:
                active_coupons = json.load(f)
        except: pass

    total_profit, turnover = 0.0, 0.0
    wins, losses = 0, 0
    chart_data = []
    profit_24h = 0.0
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)

    for bet in history:
        prof = float(bet.get('profit', 0))
        stk = float(bet.get('stake', 0))
        total_profit += prof
        turnover += stk
        chart_data.append(round(total_profit, 2))
        if prof > 0: wins += 1
        elif prof < 0: losses += 1
        b_time = bet.get('time') or bet.get('date')
        if b_time:
            try:
                dt_obj = datetime.fromisoformat(b_time.replace("Z", "+00:00"))
                if dt_obj > yesterday: profit_24h += prof
            except: pass

    win_rate = round((wins/len(history)*100) if len(history) > 0 else 0, 1)
    yield_val = round((total_profit/turnover*100) if turnover > 0 else 0, 2)
    bankroll_now = STARTING_BANKROLL + total_profit
    
    # --- POPRAWKA DLA DASHBOARDU WWW ---
    # Przygotowujemy listę aktywnych kuponów bez błędów "undefined"
    clean_active = []
    for c in active_coupons:
        clean_active.append({
            "home": c.get('home', '???'),
            "away": c.get('away', '???'),
            "outcome": c.get('outcome', 'Czekam...'), # Zamiast undefined
            "odds": c.get('odds', '0.00'),            # Zamiast undefined
            "time": c.get('time', ''),
            "sport": c.get('sport', '')
        })

    web_stats = {
        "zysk_total": round(total_profit, 2),
        "zysk_24h": round(profit_24h, 2),
        "skutecznosc": win_rate,
        "yield": yield_val,
        "roi": round((total_profit/STARTING_BANKROLL)*100, 2),
        "obrot": round(turnover, 2),
        "total_bets_count": len(history),
        "wykres": chart_data,
        "active_bets": clean_active, # Przesyłamy "czyste" aktywne typy
        "last_sync": datetime.now(timezone.utc).strftime("%H:%M:%S")
    }
    
    with open('stats.json', 'w', encoding='utf-8') as f:
        json.dump(web_stats, f, indent=4)

    # Budowanie raportu Telegram
    msg = [
        "📊 <b>STATYSTYKI</b>",
        "━━━━━━━━━━━━━━━",
        f"🏦 BANKROLL: <b>{bankroll_now:.2f} PLN</b>",
        f"💰 Zysk Total: <b>{total_profit:.2f} PLN</b>",
        f"📅 Ostatnie 24h: <b>{'+' if profit_24h > 0 else ''}{profit_24h:.2f} PLN</b>",
        f"🎯 Skuteczność: <b>{win_rate}%</b>",
        f"📈 Yield: <b>{yield_val}%</b>",
        "━━━━━━━━━━━━━━━",
        "📝 <b>OSTATNIE WYNIKI:</b>"
    ]

    for bet in history[-10:]:
        p = float(bet.get('profit', 0))
        icon = "✅" if p > 0 else ("❌" if p < 0 else "⚠️")
        score = bet.get('score', '?-?')
        msg.append(f"{icon} {bet.get('home')} - {bet.get('away')} | {score} | {'+' if p > 0 else ''}{p:.2f}")

    msg.append("━━━━━━━━━━━━━━━")
    return True, "\n".join(msg)

if __name__ == "__main__":
    success, text = generate_stats()
    if success and TOKEN and CHAT_TARGET:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                      json={"chat_id": CHAT_TARGET, "text": text, "parse_mode": "HTML"})
