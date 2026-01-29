import json
import os
import requests
from datetime import datetime, timedelta, timezone

# --- KONFIGURACJA ---
TOKEN = os.getenv("T_TOKEN")
CHAT_STATS = os.getenv("T_CHAT_STATS")
STARTING_BANKROLL = 5000.0  # Kwota bazowa do obliczeń ROI

def get_upcoming_count():
    """Liczy mecze z coupons.json zaplanowane na najbliższe 12h"""
    count = 0
    now = datetime.now(timezone.utc)
    limit = now + timedelta(hours=12)
    filename = 'coupons.json'
    
    if not os.path.exists(filename):
        return 0
    
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            coupons = json.load(f)
            if isinstance(coupons, list):
                for coupon in coupons:
                    # Pomijamy NBA
                    if "basketball_nba" in str(coupon.get('sport', '')).lower():
                        continue
                    
                    time_str = coupon.get('time')
                    if time_str:
                        try:
                            # Format ISO: 2026-01-29T19:15:00Z
                            event_time = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                            if now <= event_time <= limit:
                                count += 1
                        except:
                            continue
    except:
        pass
    return count

def generate_stats():
    if not os.path.exists('history.json'):
        return None, "❌ Brak history.json"
        
    try:
        with open('history.json', 'r', encoding='utf-8') as f:
            history = json.load(f)
    except Exception as e:
        return None, f"❌ Błąd odczytu history: {e}"

    # Sprawdzenie dla Silent Update (czy przybyły nowe rozliczone mecze)
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
        # Filtracja NBA i VOID
        if "basketball_nba" in str(bet.get('sport', '')).lower(): continue
        if str(bet.get('status', '')).upper() == "VOID": continue

        prof = float(bet.get('profit', 0))
        stk = float(bet.get('stake', 0))
        total_profit += prof
        total_turnover += stk
        
        icon = "✅" if prof > 0 else "❌"
        if prof > 0: wins += 1
        else: losses += 1
        series_icons.append(icon)

        # Statystyki 24h
        try:
            b_time = bet.get('time') or bet.get('date')
            if datetime.fromisoformat(b_time.replace("Z", "+00:00")) > yesterday:
                profit_24h += prof
        except: pass

        processed_matches.append(f"{icon} {bet.get('home')}-{bet.get('away')} | `{prof:+.2f} PLN`")

    total_bets = wins + losses
    upcoming = get_upcoming_count()
    
    # Obliczenia wskaźników
    yield_val = (total_profit / total_turnover * 100) if total_turnover > 0 else 0
    roi_val = (total_profit / STARTING_BANKROLL * 100) if STARTING_BANKROLL > 0 else 0
    win_rate = (wins / total_bets * 100) if total_bets > 0 else 0

    # Dane do index.html
    web_data = {
        "total_profit": round(total_profit, 2),
        "profit_24h": round(profit_24h, 2),
        "yield": round(yield_val, 2),
        "roi": round(roi_val, 2),
        "turnover": round(total_turnover, 2),
        "win_rate": round(win_rate, 1),
        "total_bets": total_bets,
        "upcoming_count": upcoming,
        "last_update": now.strftime("%H:%M:%S")
    }

    with open('stats.json', 'w', encoding='utf-8') as f:
        json.dump(web_data, f, indent=4)

    # Raport Telegram
    diff = total_bets - old_total_bets
    report = [
        "📊 *DASHBOARD STATYSTYK*",
        "━━━━━━━━━━━━━━━",
        f"💰 *Zysk Total:* `{total_profit:.2f} PLN`",
        f"📈 *Yield:* `{yield_val:.2f}%` | *ROI:* `{roi_val:.2f}%`",
        f"🔄 *Obrót:* `{total_turnover:.2f} PLN`",
        f"🕒 *W grze (12h):* `{upcoming} typów`",
        f"🎯 *Skuteczność:* `{win_rate:.1f}%` ({wins}/{total_bets})",
        f"🔥 *Ostatnie:* {''.join(series_icons[-10:])}",
        "━━━━━━━━━━━━━━━"
    ]

    if diff > 0:
        report.append(f"📝 *NOWE ({diff}):*")
        report.extend(processed_matches[-diff:])
    else:
        report.append("📝 *OSTATNIE WYNIKI:*")
        report.extend(processed_matches[-5:])

    return (diff > 0), "\n".join(report)

if __name__ == "__main__":
    should_send, text = generate_stats()
    if should_send and TOKEN and CHAT_STATS:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                     json={"chat_id": CHAT_STATS, "text": text, "parse_mode": "Markdown"})
