import json
import os
import requests
from datetime import datetime, timedelta, timezone

# ================= KONFIGURACJA =================
TOKEN = os.getenv("T_TOKEN")
CHAT_STATS = os.getenv("T_CHAT_STATS")
STARTING_BANKROLL = 5000.0  # Twoja kwota bazowa (do obliczeń ROI/Bankroll)

def generate_stats():
    filename = 'history.json'
    
    if not os.path.exists(filename):
        print(f"❌ Błąd: Plik {filename} nie istnieje.")
        return

    try:
        with open(filename, 'r', encoding='utf-8') as f:
            history = json.load(f)
    except Exception as e:
        print(f"❌ Błąd odczytu pliku history: {e}")
        return

    if not isinstance(history, list) or len(history) == 0:
        print("ℹ️ Historia jest pusta. Brak statystyk do wygenerowania.")
        return

    # --- OBLICZENIA ---
    total_profit = 0.0
    total_turnover = 0.0
    wins = 0
    
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)
    profit_24h = 0.0

    for bet in history:
        prof = float(bet.get('profit', 0))
        stk = float(bet.get('stake', 0))
        
        total_profit += prof
        total_turnover += stk
        if prof > 0:
            wins += 1
            
        # Zysk z ostatnich 24h
        try:
            b_time_str = bet.get('time', '')
            if b_time_str:
                b_time = datetime.fromisoformat(b_time_str.replace("Z", "+00:00"))
                if b_time > yesterday:
                    profit_24h += prof
        except:
            pass

    # Wskaźniki
    current_bankroll = STARTING_BANKROLL + total_profit
    win_rate = (wins / len(history) * 100) if history else 0
    yield_val = (total_profit / total_turnover * 100) if total_turnover > 0 else 0

    # --- FORMATOWANIE LISTY OSTATNICH 10 WYNIKÓW ---
    last_10 = history[-10:]
    results_list = []
    
    for bet in last_10:
        icon = "✅" if float(bet.get('profit', 0)) > 0 else "❌"
        home = bet.get('home', '???')
        away = bet.get('away', '???')
        score = bet.get('score', '0:0')
        prof = float(bet.get('profit', 0))
        
        # Format: ❌ Team A - Team B | 1:2 | -350.00
        results_list.append(f"{icon} {home} - {away} | {score} | {prof:+.2f}")

    # --- BUDOWANIE RAPORTU ---
    report = [
        "📊 <b>STATYSTYKI</b>",
        "━━━━━━━━━━━━━━━",
        f"🏦 <b>BANKROLL:</b> <code>{current_bankroll:.2f} PLN</code>",
        f"💰 <b>Zysk Total:</b> <code>{total_profit:.2f} PLN</code>",
        f"📅 <b>Ostatnie 24h:</b> <code>{profit_24h:+.2f} PLN</code>",
        f"🎯 <b>Skuteczność:</b> <code>{win_rate:.1f}%</code>",
        f"📈 <b>Yield:</b> <code>{yield_val:.2f}%</code>",
        "━━━━━━━━━━━━━━━",
        "📝 <b>OSTATNIE WYNIKI:</b>",
        "\n".join(results_list),
        "━━━━━━━━━━━━━━━"
    ]

    full_message = "\n".join(report)

    # --- WYSYŁKA ---
    if TOKEN and CHAT_STATS:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        payload = {
            "chat_id": CHAT_STATS,
            "text": full_message,
            "parse_mode": "HTML"
        }
        try:
            r = requests.post(url, json=payload, timeout=10)
            if r.status_code == 200:
                print("✅ Raport wysłany na Telegram.")
            else:
                print(f"❌ Błąd Telegram API: {r.status_code} - {r.text}")
        except Exception as e:
            print(f"❌ Błąd połączenia: {e}")
    else:
        print("⚠️ Brak konfiguracji TOKEN/CHAT_STATS. Wydruk do konsoli:")
        print(full_message)

if __name__ == "__main__":
    generate_stats()
