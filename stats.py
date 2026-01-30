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
            
        # --- NOWE: Pobieranie aktualnego salda pod Challenge ---
        current_bankroll = 100.0
        if os.path.exists('bankroll.json'):
            with open('bankroll.json', 'r') as f:
                br_data = json.load(f)
                current_bankroll = br_data.get("balance", 100.0)
    except Exception as e:
        return f"❌ Błąd krytyczny: {e}"

    if not history:
        return "ℹ️ Brak danych w historii do wygenerowania statystyk."

    total_profit = 0.0
    total_turnover = 0.0
    profit_24h = 0.0
    wins, losses, voids = 0, 0, 0
    last_matches_list = []
    
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)

    for bet in reversed(history):
        status = str(bet.get('status', '')).upper()
        if status == "VOID":
            voids += 1
            continue

        try:
            profit = float(bet.get('profit', 0))
            stake = float(bet.get('stake', 0))
            
            total_profit += profit
            total_turnover += stake
            
            if profit > 0:
                wins += 1
                icon = "✅"
            elif profit < 0:
                losses += 1
                icon = "❌"
            else:
                icon = "⚪"

            bet_date_str = bet.get('time') or bet.get('date')
            if bet_date_str:
                try:
                    if "T" in bet_date_str:
                        bet_date = datetime.fromisoformat(bet_date_str.replace("Z", "+00:00"))
                    else:
                        bet_date = datetime.strptime(bet_date_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                    
                    if bet_date > yesterday:
                        profit_24h += profit
                except:
                    pass

            if len(last_matches_list) < 5:
                home = bet.get('home') or bet.get('home_team') or "???"
                away = bet.get('away') or bet.get('away_team') or "???"
                score = bet.get('score', '?:?')
                last_matches_list.append(f"{icon} {home}-{away} ({score}) | `{profit:+.2f} PLN`")

        except (ValueError, TypeError):
            continue

    total_bets = wins + losses
    yield_val = (total_profit / total_turnover * 100) if total_turnover > 0 else 0
    win_rate = (wins / total_bets * 100) if total_bets > 0 else 0
    
    # Obliczanie następnej stawki (Twoje 5% kuli śnieżnej)
    next_stake = current_bankroll * 0.05

    report = [
        "📊 *CHALLENGE 100 PLN: STATYSTYKI*",
        "━━━━━━━━━━━━━━━",
        f"🏦 *AKTUALNY BANKROLL:* `{current_bankroll:.2f} PLN`",
        f"❄️ *Następna stawka (5%):* `{next_stake:.2f} PLN`",
        "━━━━━━━━━━━━━━━",
        f"💰 *Zysk 24h:* `{profit_24h:+.2f} PLN`",
        f"💎 *Zysk całkowity:* `{total_profit:.2f} PLN`",
        f"📈 *Yield:* `{yield_val:.2f}%`",
        f"🎯 *Skuteczność:* `{win_rate:.1f}%` ({wins}/{total_bets})",
        "━━━━━━━━━━━━━━━",
        "📝 *OSTATNIE ROZLICZENIA:*",
    ]
    
    if last_matches_list:
        report.extend(last_matches_list)
    else:
        report.append("_Brak rozliczonych meczów_")
        
    report.append("━━━━━━━━━━━━━━━")
    report.append(f"🕒 _Aktualizacja: {datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC_")

    return "\n".join(report)
