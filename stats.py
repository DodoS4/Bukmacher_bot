import json
import os
import requests
from datetime import datetime, timedelta, timezone

def generate_stats():
    try:
        if not os.path.exists('history.json'):
            return None, "❌ Błąd: Nie znaleziono pliku history.json"
            
        with open('history.json', 'r', encoding='utf-8') as f:
            history = json.load(f)
    except Exception as e:
        return None, f"❌ Błąd krytyczny: {e}"

    # Wczytujemy poprzednie statystyki do porównania
    old_total_bets = 0
    if os.path.exists('stats.json'):
        try:
            with open('stats.json', 'r', encoding='utf-8') as f:
                old_data = json.load(f)
                old_total_bets = old_data.get('total_bets', 0)
        except:
            pass

    total_profit = 0.0
    total_turnover = 0.0
    profit_24h = 0.0
    wins, losses = 0, 0
    processed_matches = []
    series_icons = [] # Do śledzenia formy (ostatnie 10)
    
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)

    for bet in history:
        sport_key = str(bet.get('sport', '')).lower()
        if "basketball_nba" in sport_key:
            continue

        status = str(bet.get('status', '')).upper()
        if status == "VOID":
            continue

        profit = float(bet.get('profit', 0))
        stake = float(bet.get('stake', 0))
        total_profit += profit
        total_turnover += stake
        
        icon = "✅" if profit > 0 else "❌"
        if profit > 0: wins += 1
        else: losses += 1
        
        series_icons.append(icon)

        # Statystyki 24h
        try:
            b_time = bet.get('time') or bet.get('date')
            b_date = datetime.fromisoformat(b_time.replace("Z", "+00:00"))
            if b_date > yesterday:
                profit_24h += profit
        except: pass

        home = bet.get('home') or "???"
        away = bet.get('away') or "???"
        score = bet.get('score', '')
        processed_matches.append(f"{icon} {home}-{away} ({score}) | `{profit:+.2f} PLN`")

    total_bets = wins + losses
    yield_val = (total_profit / total_turnover * 100) if total_turnover > 0 else 0
    win_rate = (wins / total_bets * 100) if total_bets > 0 else 0
    
    # Ostatnia forma (10 meczów)
    form_string = "".join(series_icons[-10:])

    web_data = {
        "total_profit": round(total_profit, 2),
        "profit_24h": round(profit_24h, 2),
        "yield": round(yield_val, 2),
        "win_rate": round(win_rate, 1),
        "turnover": round(total_turnover, 2),
        "total_bets": total_bets,
        "last_update": now.strftime("%H:%M:%S")
    }
    with open('stats.json', 'w', encoding='utf-8') as f:
        json.dump(web_data, f, indent=4)

    diff = total_bets - old_total_bets
    should_send_telegram = (diff > 0)

    report = [
        "📊 *OFICJALNE STATYSTYKI*",
        "━━━━━━━━━━━━━━━",
        f"💰 *Zysk 24h:* `{profit_24h:+.2f} PLN`",
        f"💎 *Zysk całkowity:* `{total_profit:.2f} PLN`",
        f"📈 *Yield:* `{yield_val:.2f}%` | *WR:* `{win_rate:.1f}%`",
        f"🔥 *Ostatnia forma:* {form_string}",
        "━━━━━━━━━━━━━━━",
    ]

    if diff > 0:
        report.append(f"📝 *NOWE ROZLICZENIA ({diff}):*")
        report.extend(processed_matches[-diff:])
    else:
        report.append("📝 *OSTATNIE ROZLICZENIA:*")
        report.extend(processed_matches[-5:])

    report.append("━━━━━━━━━━━━━━━")
    report.append(f"🕒 _Aktualizacja: {now.strftime('%H:%M:%S')} UTC_")

    return should_send_telegram, "\n".join(report)

if __name__ == "__main__":
    token = os.getenv("T_TOKEN")
    chat_stats_id = os.getenv("T_CHAT_STATS") or os.getenv("T_CHAT_RESULTS")
    
    should_send, report_text = generate_stats()
    
    print(f"DEBUG: Nowych meczów: {should_send}")
    
    if should_send:
        if token and chat_stats_id:
            requests.post(f"https://api.telegram.org/bot{token}/sendMessage", 
                         json={"chat_id": chat_stats_id, "text": report_text, "parse_mode": "Markdown"})
