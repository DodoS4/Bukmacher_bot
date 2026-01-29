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
        return "ℹ️ Brak danych w historii do wygenerowania statystyk."

    # Inicjalizacja liczników
    total_profit = 0.0
    total_turnover = 0.0
    profit_24h = 0.0
    wins, losses = 0, 0
    last_matches_list = []
    
    # Czas do obliczeń 24h
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)

    # Procesujemy historię
    for bet in reversed(history):
        # --- FILTR NBA: Pomijamy te mecze w statystykach ---
        sport_key = str(bet.get('sport', '')).lower()
        if "basketball_nba" in sport_key:
            continue

        status = str(bet.get('status', '')).upper()
        if status == "VOID":
            continue

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

            # Obliczanie zysku z ostatnich 24h
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

            # Lista 5 ostatnich rozliczeń
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

    # ZAPIS DANYCH DO PLIKU DLA STRONY WWW (stats.json)
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

    # Budowanie raportu tekstowego (Usunięto napis "BEZ NBA")
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
    
    if last_matches_list:
        report.extend(last_matches_list)
    else:
        report.append("_Brak rozliczonych meczów_")
        
    report.append("━━━━━━━━━━━━━━━")
    report.append(f"🕒 _Aktualizacja: {now.strftime('%H:%M:%S')} UTC_")

    return "\n".join(report)

if __name__ == "__main__":
    # T_TOKEN zostaje ten sam, ale wysyłamy na T_CHAT_STATS
    token = os.getenv("T_TOKEN")
    chat_stats_id = os.getenv("T_CHAT_RESULTS")
    
    report_text = generate_stats()
    
    # Wyświetlenie w logach GitHub Actions
    print(report_text)
    
    if token and chat_stats_id:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_stats_id,
            "text": report_text,
            "parse_mode": "Markdown"
        }
        try:
            r = requests.post(url, json=payload, timeout=10)
            if r.status_code != 200:
                print(f"❌ Błąd Telegram API: {r.text}")
        except Exception as e:
            print(f"❌ Wyjątek przy wysyłce: {e}")
