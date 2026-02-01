import json
import os
import requests
from datetime import datetime, timedelta, timezone

# ================= ODCZYT Z SECRETS =================
TOKEN = os.getenv("T_TOKEN")
CHAT_ID = os.getenv("T_CHAT_RESULTS")
STARTING_BANKROLL = 5000.0

def generate_stats():
    filename = 'history.json'
    
    if not os.path.exists(filename):
        print("❌ Brak history.json")
        return

    try:
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if not content:
                print("ℹ️ Plik history.json jest pusty.")
                return
            history = json.loads(content)
            
        # Zabezpieczenie przed błędem "string indices must be integers"
        if isinstance(history, str):
            history = json.loads(history)
            
        if not isinstance(history, list):
            print("❌ Dane w history.json nie są listą!")
            return
            
    except Exception as e:
        print(f"❌ Błąd krytyczny JSON: {e}")
        return

    if not history:
        print("ℹ️ Historia jest pusta.")
        return

    # --- LOGIKA OBLICZEŃ ---
    total_profit = 0.0
    total_turnover = 0.0
    wins = 0
    
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)
    profit_24h = 0.0

    for bet in history:
        # Dodatkowe sprawdzenie czy 'bet' jest słownikiem
        if not isinstance(bet, dict):
            continue
            
        prof = float(bet.get('profit', 0))
        stk = float(bet.get('stake', 0))
        
        total_profit += prof
        total_turnover += stk
        if prof > 0:
            wins += 1
            
        # Zysk 24h
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

    # --- LISTA WYNIKÓW (Ostatnie 10) ---
    results_list = []
    # Pobieramy ostatnie 10 elementów, upewniając się, że to słowniki
    last_10 = [b for b in history if isinstance(b, dict)][-10:]
    
    for bet in last_10:
        icon = "✅" if float(bet.get('profit', 0)) > 0 else "❌"
        home = bet.get('home', '???')
        away = bet.get('away', '???')
        score = bet.get('score', '0:0')
        p = float(bet.get('profit', 0))
        results_list.append(f"{icon} {home} - {away} | {score} | {p:+.2f}")

    # --- FORMATOWANIE WIADOMOŚCI ---
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
        "\n".join(results_list) if results_list else "Brak wyników",
        "━━━━━━━━━━━━━━━"
    ]

    full_message = "\n".join(report)

    # --- WYSYŁKA ---
    if TOKEN and CHAT_ID:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        try:
            resp = requests.post(url, json={
                "chat_id": CHAT_ID,
                "text": full_message,
                "parse_mode": "HTML"
            }, timeout=10)
            if resp.status_code == 200:
                print("✅ Raport wysłany pomyślnie!")
            else:
                print(f"❌ Błąd Telegrama: {resp.text}")
        except Exception as e:
            print(f"❌ Błąd połączenia: {e}")
    else:
        print("❌ Brak TOKEN lub CHAT_ID w Secrets!")

if __name__ == "__main__":
    generate_stats()
