import json
import os
from datetime import datetime, timedelta, timezone

HISTORY_FILE = "history.json"
STATS_JSON_FILE = "stats.json" # Plik dla Twojej strony WWW

def generate_stats():
    if not os.path.exists(HISTORY_FILE): 
        print("ℹ️ Brak pliku historii do przetworzenia.")
        return

    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        history = json.load(f)
    if not history: 
        print("ℹ️ Historia jest pusta.")
        return

    # --- OBLICZENIA ---
    total_profit = sum(m.get('profit', 0) for m in history)
    base_capital = 5000 
    bankroll = base_capital + total_profit
    
    wins = sum(1 for m in history if m.get('status') == 'WIN')
    losses = sum(1 for m in history if m.get('status') == 'LOSS')
    total_matches = wins + losses
    
    accuracy = (wins / total_matches * 100) if total_matches > 0 else 0
    total_staked = sum(m.get('stake', 0) for m in history if m.get('status') in ['WIN', 'LOSS'])
    yield_val = (total_profit / total_staked * 100) if total_staked > 0 else 0

    # Zysk z ostatnich 24h
    now = datetime.now(timezone.utc)
    last_24h_profit = 0
    for m in history:
        try:
            m_time = datetime.fromisoformat(m['time'].replace("Z", "+00:00"))
            if now - m_time < timedelta(hours=24):
                last_24h_profit += m.get('profit', 0)
        except: continue

    # --- PRZYGOTOWANIE DANYCH POD WWW (stats.json) ---
    stats_data = {
        "bankroll": round(bankroll, 2),
        "total_profit": round(total_profit, 2),
        "last_24h": round(last_24h_profit, 2),
        "accuracy": round(accuracy, 1),
        "yield": round(yield_val, 2),
        "total_matches": total_matches,
        "last_update": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "history_preview": history[-10:] # Ostatnie 10 meczów dla tabeli na stronie
    }

    # Zapisujemy do pliku, który GitHub Pages wykorzystuje do wyświetlania statystyk
    with open(STATS_JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(stats_data, f, indent=4)
    
    print(f"✅ Statystyki zaktualizowane w {STATS_JSON_FILE}. (Telegram uciszony)")

if __name__ == "__main__":
    generate_stats()
