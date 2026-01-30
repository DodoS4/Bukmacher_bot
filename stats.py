import json
import os
import requests
from datetime import datetime, timedelta, timezone

# ================= PANCERNA KONFIGURACJA =================
def get_env_safe(name):
    val = os.environ.get(name) or os.getenv(name)
    return str(val).strip() if val and len(str(val).strip()) > 0 else None

TOKEN = get_env_safe("T_TOKEN")
# Celowo używamy T_CHAT_RESULTS dla statystyk
CHAT_TARGET = get_env_safe("T_CHAT_RESULTS") or get_env_safe("T_CHAT")

STARTING_BANKROLL = 5000.0

def get_upcoming_count():
    count = 0
    now = datetime.now(timezone.utc)
    if not os.path.exists('coupons.json'): return 0
    try:
        with open('coupons.json', 'r', encoding='utf-8') as f:
            coupons = json.load(f)
            for c in coupons:
                t = c.get('time')
                if t:
                    ev_time = datetime.fromisoformat(t.replace("Z", "+00:00"))
                    if now <= ev_time <= (now + timedelta(hours=12)): count += 1
    except: pass
    return count

def generate_stats():
    print("🔍 Generowanie raportu z listą meczów...")
    if not os.path.exists('history.json'): 
        return False, "❌ Brak danych historycznych."
        
    try:
        with open('history.json', 'r', encoding='utf-8') as f:
            history = json.load(f)
    except Exception as e:
        return False, f"❌ Błąd: {e}"

    total_profit, total_turnover, profit_24h = 0.0, 0.0, 0.0
    wins, losses = 0, 0
    series_icons = []
    match_list = []
    
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)

    for bet in history:
        # Pomiń NBA jeśli chcesz czysty hokej/piłkę
        if "nba" in str(bet.get('sport', '')).lower(): continue
        
        prof = float(bet.get('profit', 0))
        stk = float(bet.get('stake', 0))
        total_profit += prof
        total_turnover += stk
        
        icon = "✅" if prof > 0 else "❌"
        if prof > 0: wins += 1
        else: losses += 1
        series_icons.append(icon)

        # Sprawdzanie profitu z 24h
        b_time = bet.get('time') or bet.get('date')
        if b_time:
            try:
                dt_obj = datetime.fromisoformat(b_time.replace("Z", "+00:00"))
                if dt_obj > yesterday:
                    profit_24h += prof
            except: pass

        # Dodawanie meczu do listy raportu
        res_str = f"{icon} {bet.get('home')} - {bet.get('away')} | <b>{bet.get('score', '?-?')}</b> | <code>{prof:+.2f}</code>"
        match_list.append(res_str)

    total_bets = len(series_icons)
    
    # Budowanie wiadomości
    report = [
        "📊 <b>DASHBOARD STATYSTYK</b>",
        f"━━━━━━━━━━━━━━━",
        f"💰 Zysk Total: <b>{total_profit:.2f} PLN</b>",
        f"📅 Ostatnie 24h: <b>{profit_24h:+.2f} PLN</b>",
        f"🎯 Skuteczność: <b>{round((wins/total_bets*100) if total_bets > 0 else 0, 1)}%</b>",
        f"📈 Yield: <b>{round((total_profit/total_turnover*100) if total_turnover > 0 else 0, 2)}%</b>",
        f"🕒 W grze: <b>{get_upcoming_count()}</b>",
        f"━━━━━━━━━━━━━━━",
        "📝 <b>OSTATNIE WYNIKI:</b>"
    ]
    
    # Dodaj 10 ostatnich meczów z historii
    report.extend(match_list[-10:])
    
    report.append(f"━━━━━━━━━━━━━━━")
    report.append(f"🔥 <b>Seria:</b> {''.join(series_icons[-15:])}")

    return True, "\n".join(report)

if __name__ == "__main__":
    success, text = generate_stats()
    
    if TOKEN and CHAT_TARGET:
        print(f"📤 Wysyłanie raportu na kanał wyników: {CHAT_TARGET[:8]}...")
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
            json={"chat_id": CHAT_TARGET, "text": text, "parse_mode": "HTML"}
        )
