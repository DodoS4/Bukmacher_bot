import json

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
    wins, losses = 0, 0
    last_matches_list = []

    # Iterujemy od końca, aby znaleźć 5 najnowszych rozliczonych meczów
    for bet in reversed(history):
        if bet.get('outcome') == "Draw":
            continue

        try:
            profit = float(bet.get('profit', 0))
            stake = float(bet.get('stake', 0))
        except (ValueError, TypeError):
            continue

        if profit != 0:
            total_profit += profit
            total_turnover += stake
            
            if profit > 0:
                wins += 1
                icon = "✅"
            else:
                losses += 1
                icon = "❌"

            # Dodajemy tylko 5 ostatnich do listy podglądu
            if len(last_matches_list) < 5:
                home = bet.get('home_team', '???')
                away = bet.get('away_team', '???')
                score = bet.get('score', 'N/A')
                entry = f"{icon} {home} - {away} ({score}) | `{profit:+.2f} PLN`"
                last_matches_list.append(entry)

    # Obliczenia
    total_bets = wins + losses
    yield_val = (total_profit / total_turnover * 100) if total_turnover > 0 else 0
    win_rate = (wins / total_bets * 100) if total_bets > 0 else 0

    # BUDOWANIE RAPORTU
    report = [
        "📊 *OFICJALNE STATYSTYKI*",
        "━━━━━━━━━━━━━━━",
        f"💰 *Zysk całkowity:* `{total_profit:.2f} PLN`",
        f"📈 *Yield:* `{yield_val:.2f}%`",
        f"🎯 *Skuteczność:* `{win_rate:.1f}%` ({wins}/{total_bets})",
        f"🔄 *Obrót:* `{total_turnover:.2f} PLN`",
        "━━━━━━━━━━━━━━━",
        "📝 *OSTATNIE ROZLICZENIA:*",
    ]
    
    # Odwracamy listę 5 meczów, aby najnowszy był na samym dole (opcjonalnie)
    # last_matches_list.reverse() 

    if last_matches_list:
        report.extend(last_matches_list)
    else:
        report.append("_Brak rozliczonych meczów_")
        
    report.append("━━━━━━━━━━━━━━━")
    report.append("ℹ️ _Statystyki generowane automatycznie_")

    return "\n".join(report)

if __name__ == "__main__":
    print(generate_stats())
