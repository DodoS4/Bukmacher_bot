import json
from datetime import datetime, timedelta

def generate_stats():
    try:
        with open('history.json', 'r', encoding='utf-8') as f:
            history = json.load(f)
    except FileNotFoundError:
        return "❌ Błąd: Nie znaleziono pliku history.json"
    except Exception as e:
        return f"❌ Błąd krytyczny: {e}"

    total_profit = 0.0
    total_turnover = 0.0
    profit_24h = 0.0
    wins, losses = 0, 0
    last_matches_list = []
    
    # Czas do obliczeń 24h
    now = datetime.now()
    yesterday = now - timedelta(days=1)

    for bet in reversed(history):
        if bet.get('outcome') == "Draw":
            continue

        try:
            profit = float(bet.get('profit', 0))
            stake = float(bet.get('stake', 0))
            
            # Obliczanie zysku z ostatnich 24h
            # Zakładamy format daty: "YYYY-MM-DD HH:MM:SS"
            bet_date_str = bet.get('date') or bet.get('time')
            if bet_date_str:
                try:
                    # Próba dopasowania różnych formatów daty
                    if "T" in bet_date_str: # Format ISO
                        bet_date = datetime.fromisoformat(bet_date_str.replace("Z", "+00:00")).replace(tzinfo=None)
                    else:
                        bet_date = datetime.strptime(bet_date_str, "%Y-%m-%d %H:%M:%S")
                    
                    if bet_date > yesterday:
                        profit_24h += profit
                except:
                    pass
        except (ValueError, TypeError):
            continue

    # Druga pętla dla statystyk ogólnych i listy (aby zachować poprawną kolejność)
    for bet in reversed(history):
        if bet.get('outcome') == "Draw": continue
        profit = float(bet.get('profit', 0))
        if profit != 0:
            total_profit += profit
            total_turnover += float(bet.get('stake', 0))
            if profit > 0:
                wins += 1
                icon = "✅"
            else:
                losses += 1
                icon = "❌"

            if len(last_matches_list) < 5:
                home = bet.get('home') or bet.get('home_team') or "???"
                away = bet.get('away') or bet.get('away_team') or "???"
                match_name = bet.get('match') or f"{home} - {away}"
                score = bet.get('score', '0:0')
                last_matches_list.append(f"{icon} {match_name} ({score}) | `{profit:+.2f} PLN`")

    total_bets = wins + losses
    yield_val = (total_profit / total_turnover * 100) if total_turnover > 0 else 0
    win_rate = (wins / total_bets * 100) if total_bets > 0 else 0

    # Tworzenie raportu
    report = [
        "📊 *OFICJALNE STATYSTYKI*",
        "━━━━━━━━━━━━━━━",
        f"💰 *Zysk 24h:* `{profit_24h:+.2f} PLN`",
        f"💎 *Zysk całkowity:* `{total_profit:.2f} PLN`",
        f"📈 *Yield:* `{yield_val:.2f}%`",
        f"🎯 *Skuteczność:* `{win_rate:.1f}%` ({wins}/{total_bets})",
        f"🔄 *Obrót:* `{total_turnover:.2f} PLN`",
        "━━━━━━━━━━━━━━━",
        "📝 *OSTATNIE ROZLICZENIA:*",
    ]
    
    report.extend(last_matches_list if last_matches_list else ["_Brak rozliczonych meczów_"])
    report.append("━━━━━━━━━━━━━━━")
    report.append(f"🕒 _Aktualizacja: {now.strftime('%H:%M:%S')}_")

    return "\n".join(report)
