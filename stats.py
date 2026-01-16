import json
import os
import requests
from datetime import datetime, timedelta, timezone
from collections import defaultdict

# Konfiguracja
RESULTS_FILE = "history.json"
TELEGRAM_TOKEN = os.getenv("T_TOKEN")
TELEGRAM_CHAT = os.getenv("T_CHAT_RESULTS")

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Błąd wysyłki statystyk: {e}")

def load_results():
    try:
        with open(RESULTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def generate_report(results, days=7):
    if not results:
        return "Brak danych do raportu."

    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days)
    
    # Filtrowanie po dacie (jeśli masz datę w wynikach)
    filtered = []
    for r in results:
        # Zakładamy, że data jest w formacie ISO z settle.py
        try:
            r_date = datetime.fromisoformat(r["date"].replace("Z", "+00:00"))
            if r_date >= since:
                filtered.append(r)
        except:
            filtered.append(r) # fallback jeśli brak daty

    if not filtered:
        return f"Brak wyników w ostatnich {days} dniach."

    total_profit = 0
    total_bets = len(filtered)
    wins = 0
    
    # Statystyki per sport/liga
    stats = defaultdict(lambda: {"count": 0, "profit": 0, "wins": 0})

    for r in filtered:
        profit = r["profit"]
        # Przyjmujemy nazwę sportu z klucza lub wyciągamy z meczu
        sport = r.get("sport", "Inne")
        
        stats[sport]["count"] += 1
        stats[sport]["profit"] += profit
        if profit > 0:
            stats[sport]["wins"] += 1
            wins += 1
        total_profit += profit

    # Budowanie wiadomości HTML
    msg = f"📊 <b>RAPORT Z OSTATNICH {days} DNI</b>\n"
    msg += "━━━━━━━━━━━━━━━━━━\n"
    
    for sport, s in stats.items():
        win_rate = (s["wins"] / s["count"]) * 100
        emoji = "📈" if s["profit"] > 0 else "📉"
        msg += f"{emoji} <b>{sport}</b>: {s['profit']:+.2f} PLN\n"
        msg += f"   Skuteczność: {win_rate:.1f}% ({s['count']} typów)\n\n"

    msg += "━━━━━━━━━━━━━━━━━━\n"
    total_win_rate = (wins / total_bets) * 100
    color = "🟢" if total_profit > 0 else "🔴"
    msg += f"{color} <b>SUMA: {total_profit:+.2f} PLN</b>\n"
    msg += f"🎯 Total WinRate: <b>{total_win_rate:.1f}%</b>"

    return msg

if __name__ == "__main__":
    results = load_results()
    
    # Raz w tygodniu (np. w niedzielę) wysyłaj raport tygodniowy
    # Ale domyślnie wysyłaj podsumowanie po każdym przebiegu settle.py
    report = generate_report(results, days=7)
    send_telegram(report)
