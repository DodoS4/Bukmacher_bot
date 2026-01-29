import json
import os
import requests
from datetime import datetime, timedelta, timezone

# --- KONFIGURACJA ---
TOKEN = os.getenv("T_TOKEN")
CHAT_STATS = os.getenv("T_CHAT_STATS") or os.getenv("T_CHAT_RESULTS")
STARTING_BANKROLL = 5000.0  # Kwota początkowa do obliczeń ROI

def generate_stats():
    try:
        if not os.path.exists('history.json'):
            return None, "❌ Brak history.json"
        with open('history.json', 'r', encoding='utf-8') as f:
            history = json.load(f)
    except Exception as e:
        return None, f"❌ Błąd: {e}"

    old_total_bets = 0
    if os.path.exists('stats.json'):
        try:
            with open('stats.json', 'r', encoding='utf-8') as f:
                old_total_bets = json.load(f).get('total_bets', 0)
        except: pass

    total_profit, total_turnover, profit_24h = 0.0, 0.0, 0.0
    wins, losses = 0, 0
    processed_matches, series_icons = [], []
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)

    for bet in history:
        if "basketball_nba" in str(bet.get('sport', '')).lower(): continue
        if str(bet.get('status', '')).upper() == "VOID": continue

        profit = float(bet.get('profit', 0))
        stake = float(bet.get('stake', 0))
        total_profit += profit
        total_turnover += stake
        
        icon = "✅" if profit > 0 else "❌"
        if profit > 0: wins += 1
        else: losses += 1
        series_icons.append(icon)

        try:
            b_time = bet.get('time') or bet.get('date')
            if datetime.fromisoformat(b_time.replace("Z", "+00:00")) > yesterday:
                profit_24h += profit
        except: pass

        home, away = bet.get('home', '???'), bet.get('away', '???')
        processed_matches.append(f"{icon} {home}-{away} ({bet.get('score', '')}) | `{profit:+.2f} PLN`")

    total_bets = wins + losses
    yield_val = (total_profit / total_turnover * 100) if total_turnover > 0 else 0
    roi_val = (total_profit / STARTING_BANKROLL * 100) if STARTING_BANKROLL > 0 else 0
    win_rate = (wins / total_bets * 100) if total_bets > 0 else 0

    web_data = {
        "total_profit": round(total_profit, 2),
        "profit_24h": round(profit_24h, 2),
        "yield": round(yield_val, 2),
        "roi": round(roi_val, 2),
        "turnover": round(total_turnover, 2),
        "win_rate": round(win_rate, 1),
        "total_bets": total_bets,
        "last_update": now.strftime("%H:%M:%S")
    }
    with open('stats.json', 'w', encoding='utf-8') as f:
        json.dump(web_data, f, indent=4)

    diff = total_bets - old_total_bets
    report = [
        "📊 *OFICJALNE STATYSTYKI*", "━━━━━━━━━━━━━━━",
        f"💰 *Zysk 24h:* `{profit_24h:+.2f} PLN`",
        f"💎 *Zysk całkowity:* `{total_profit:.2f} PLN`",
        f"📈 *Yield:* `{yield_val:.2f}%` | *ROI:* `{roi_val:.2f}%`",
        f"🔄 *Obrót:* `{total_turnover:.2f} PLN`",
        f"🎯 *Skuteczność:* `{win_rate:.1f}%` ({wins}/{total_bets})",
        f"🔥 *Ostatnia forma:* {''.join(series_icons[-10:])}", "━━━━━━━━━━━━━━━"
    ]
    if diff > 0:
        report.append(f"📝 *NOWE ROZLICZENIA ({diff}):*")
        report.extend(processed_matches[-diff:])
    else:
        report.append("📝 *OSTATNIE ROZLICZENIA:*")
        report.extend(processed_matches[-5:])
    report.append(f"━━━━━━━━━━━━━━━\n🕒 _Aktualizacja: {now.strftime('%H:%M:%S')} UTC_")

    return (diff > 0), "\n".join(report)

if __name__ == "__main__":
    should_send, report_text = generate_stats()
    if should_send and TOKEN and CHAT_STATS:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                     json={"chat_id": CHAT_STATS, "text": report_text, "parse_mode": "Markdown"})
