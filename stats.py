import json
import os
import requests
from datetime import datetime, timedelta, timezone

def generate_stats():
    try:
        if not os.path.exists('history.json'):
            return "❌ Błąd: Nie znaleziono pliku history.json"
            
        with open('history.json', 'r', encoding='utf-8') as f:
            history = json.load(f)
    except Exception as e:
        return f"❌ Błąd krytyczny: {e}"

    if not history:
        return "ℹ️ Brak danych."

    total_profit = 0.0
    total_turnover = 0.0
    profit_24h = 0.0
    wins, losses = 0, 0
    last_matches_list = []
    
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)

    for bet in reversed(history):
        # --- FILTR NBA ---
        sport_key = str(bet.get('sport', '')).lower()
        if "basketball_nba" in sport_key:
            continue # Pomija mecze NBA w obliczeniach
        
        if str(bet.get('status')).upper() == "VOID": 
            continue

        profit = float(bet.get('profit', 0))
        stake = float(bet.get('stake', 0))
        
        total_profit += profit
        total_turnover += stake
        
        if profit > 0: wins += 1
        else: losses += 1

        # Obliczanie zysku 24h
        try:
            b_time = bet.get('time') or bet.get('date')
            b_date = datetime.fromisoformat(b_time.replace("Z", "+00:00"))
            if b_date > yesterday:
                profit_24h += profit
        except: pass

        if len(last_matches_list) < 5:
            icon = "✅" if profit > 0 else "❌"
            home = bet.get('home') or "???"
            away = bet.get('away') or "???"
            last_matches_list.append(f"{icon} {home}-{away} | `{profit:+.2f} PLN`")

    total_bets = wins + losses
    yield_val = (total_profit / total_turnover * 100) if total_turnover > 0 else 0
    win_rate = (wins / total_bets * 100) if total_bets > 0 else 0

    # ZAPIS DO STATS.JSON DLA WWW
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

    # Raport Telegram
    report = [
        "📊 *OFICJALNE STATYSTYKI (BEZ NBA)*",
        "━━━━━━━━━━━━━━━",
        f"💰 *Zysk 24h:* `{profit_24h:+.2f} PLN`",
        f"💎 *Zysk całkowity:* `{total_profit:.2f} PLN`",
        f"📈 *Yield:* `{yield_val:.2f}%`",
        f"🎯 *Skuteczność:* `{win_rate:.1f}%` ({wins}/{total_bets})",
        f"🔄 *Obrót:* `{total_turnover:.2f} PLN`",
        "━━━━━━━━━━━━━━━",
        "📝 *OSTATNIE ROZLICZENIA:*",
    ]
    report.extend(last_matches_list)
    return "\n".join(report)

if __name__ == "__main__":
    token = os.getenv("T_TOKEN")
    chat_id = os.getenv("T_CHAT")
    report_text = generate_stats()
    print(report_text)
    
    if token and chat_id:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage", 
                     json={"chat_id": chat_id, "text": report_text, "parse_mode": "Markdown"})
