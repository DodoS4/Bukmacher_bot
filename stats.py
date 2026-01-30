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
    report.append(f"🕒 _Aktualizacja: {datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC_")

    return "\n".join(report)

if __name__ == "__main__":
    # --- KLUCZOWA ZMIANA ---
    token = os.getenv("T_TOKEN")
    # Skrypt najpierw próbuje wysłać na kanał wyników, jeśli go nie ma - na główny
    chat_id = os.getenv("T_CHAT_RESULTS") or os.getenv("T_CHAT")
    
    report_text = generate_stats()
    print(report_text)
    
    if token and chat_id:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": report_text,
            "parse_mode": "Markdown"
        }
        try:
            r = requests.post(url, json=payload, timeout=10)
            if r.status_code != 200:
                print(f"❌ Błąd Telegram API: {r.text}")
            else:
                print(f"✅ Statystyki wysłane do: {chat_id}")
        except Exception as e:
            print(f"❌ Wyjątek przy wysyłce: {e}")
