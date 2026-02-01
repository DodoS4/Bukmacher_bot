import json
import os
import requests
from datetime import datetime, timedelta, timezone

# ================= KONFIGURACJA =================
TOKEN = os.getenv("T_TOKEN")
CHAT_ID = os.getenv("T_CHAT_RESULTS")
STARTING_BANKROLL = 5000.0

def generate_stats():
    # 1. Ładowanie i weryfikacja danych
    if not os.path.exists('history.json'):
        return print("❌ Brak history.json")

    try:
        with open('history.json', 'r', encoding='utf-8') as f:
            history = json.load(f)
        if not isinstance(history, list):
            history = json.loads(history) # Obsługa błędnie zapisanego JSONa jako string
    except Exception as e:
        return print(f"❌ Błąd JSON: {e}")

    # 2. Obliczenia statystyk
    total_profit = sum(float(b.get('profit', 0)) for b in history)
    total_stake = sum(float(b.get('stake', 0)) for b in history)
    wins = sum(1 for b in history if float(b.get('profit', 0)) > 0)
    
    # Obliczanie progresji zysku dla wykresu (skumulowany zysk krok po kroku)
    skumulowany_zysk = 0
    punkty_wykresu = [0.0]
    for b in sorted(history, key=lambda x: x.get('time', '')):
        skumulowany_zysk += float(b.get('profit', 0))
        punkty_wykresu.append(round(skumulowany_zysk, 2))

    # Obliczanie zysku 24h
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)
    profit_24h = sum(float(b.get('profit', 0)) for b in history 
                    if datetime.fromisoformat(b.get('time', '').replace("Z", "+00:00")) > yesterday)

    # 3. Przygotowanie stats.json dla Twojego HTML
    # Używamy nazw kluczy, których szuka Twój JavaScript (linia 102-113 w HTML)
    web_data = {
        "zysk_total": round(total_profit, 2),
        "zysk_24h": round(profit_24h, 2),
        "roi": round((total_profit / STARTING_BANKROLL * 100), 2),
        "obrot": round(total_stake, 2),
        "yield": round((total_profit / total_stake * 100), 2) if total_stake > 0 else 0,
        "total_bets_count": len(history),
        "skutecznosc": round((wins / len(history) * 100), 1) if history else 0,
        "wykres": punkty_wykresu,
        "last_sync": datetime.now().strftime("%H:%M:%S")
    }

    with open('stats.json', 'w', encoding='utf-8') as f:
        json.dump(web_data, f, indent=4)
    print("✅ Plik stats.json został zaktualizowany.")

    # 4. Opcjonalna wysyłka raportu na Telegram
    if TOKEN and CHAT_ID:
        # Tutaj możesz dodać kod wysyłający sformatowany raport tekstowy na kanał wyników
        pass

if __name__ == "__main__":
    generate_stats()
