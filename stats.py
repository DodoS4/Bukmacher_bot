import json
import os
import requests
from datetime import datetime, timedelta, timezone

def generate_stats():
    try:
        # 1. Pobieranie Historii
        if not os.path.exists('history.json'):
            return "❌ Błąd: Nie znaleziono pliku history.json"
            
        with open('history.json', 'r', encoding='utf-8') as f:
            history = json.load(f)

        # 2. Pobieranie aktualnego Bankrolla (Challenge 100)
        current_bankroll = 100.0
        if os.path.exists('bankroll.json'):
            try:
                with open('bankroll.json', 'r') as f:
                    br_data = json.load(f)
                    current_bankroll = float(br_data.get("balance", 100.0))
            except: pass

        # 3. Pobieranie meczów "w grze" (nadchodzących)
        upcoming_count = 0
        if os.path.exists('coupons.json'):
            try:
                with open('coupons.json', 'r') as f:
                    upcoming_count = len(json.load(f))
            except: pass

    except Exception as e:
        return f"❌ Błąd krytyczny: {e}"

    if not history:
        return "ℹ️ Brak danych w historii do wygenerowania statystyk."

    # Inicjalizacja liczników
    total_profit = 0.0
    total_turnover = 0.0
    profit_24h = 0.0
    wins, losses = 0, 0
    last_matches_list = []
    
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)

    # Obliczenia na podstawie historii
    for bet in reversed(history):
        status = str(bet.get('status', '')).upper()
        if status == "VOID": continue

        try:
            profit = float(bet.get('profit', 0))
            stake = float(bet.get('stake', 0))
            
            total_profit += profit
            total_turnover += stake
            
            if profit > 0:
                wins += 1
                icon = "✅"
            else:
                losses += 1
                icon = "❌"

            # Liczenie zysku z ostatnich 24h
            bet_date_str = bet.get('time') or bet.get('date')
            if bet_date_str:
                try:
                    if "T" in bet_date_str:
                        bet_date = datetime.fromisoformat(bet_date_str.replace("Z", "+00:00"))
                    else:
                        bet_date = datetime.strptime(bet_date_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                    
                    if bet_date > yesterday:
                        profit_24h += profit
                except: pass

            # Ostatnie 5 meczów do raportu
            if len(last_matches_list) < 5:
                home = bet.get('home', '???')
                away = bet.get('away', '???')
                score = bet.get('score', '?:?')
                last_matches_list.append(f"{icon} {home}-{away} ({score}) | `{profit:+.2f} PLN`")
        except: continue

    total_bets = wins + losses
    yield_val = round((total_profit / total_turnover * 100), 2) if total_turnover > 0 else 0
    win_rate = round((wins / total_bets * 100), 1) if total_bets > 0 else 0
    roi_val = round((total_profit / 100 * 100), 1) # ROI względem wkładu 100 PLN

    # --- ZAPIS DO STATS.JSON (DLA STRONY WWW) ---
    stats_for_web = {
        "total_profit": round(total_profit, 2),
        "profit_24h": round(profit_24h, 2),
        "yield": yield_val,
        "roi": roi_val,
        "turnover": round(total_turnover, 2),
        "win_rate": win_rate,
        "total_bets": total_bets,
        "upcoming_count": upcoming_count,
        "current_bankroll": round(current_bankroll, 2), # TA LINIA JEST KLUCZOWA DLA STRONY
        "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    with open('stats.json', 'w') as f:
        json.dump(stats_for_web, f, indent=4)

    # --- GENEROWANIE RAPORTU TELEGRAM ---
    next_stake = round(current_bankroll * 0.05, 2)
    report = [
        "📊 *CHALLENGE 100 PLN: STATUS*",
        "━━━━━━━━━━━━━━━",
        f"🏦 *BANKROLL:* `{current_bankroll:.2f} PLN`",
        f"❄️ *Następna stawka (5%):* `{next_stake:.2f} PLN`",
        "━━━━━━━━━━━━━━━",
        f"💰 *Zysk 24h:* `{profit_24h:+.2f} PLN`",
        f"💎 *Zysk całkowity:* `{total_profit:.2f} PLN`",
        f"📈 *Yield:* `{yield_val}%` | *WR:* `{win_rate}%`",
        "━━━━━━━━━━━━━━━",
        "📝 *OSTATNIE ROZLICZENIA:*",
    ]
    report.extend(last_matches_list if last_matches_list else ["_Brak meczów_"])
    report.append("━━━━━━━━━━━━━━━")
    
    return "\n".join(report)

if __name__ == "__main__":
    # Test lokalny
    print(generate_stats())
