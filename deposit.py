import json
import os
import sys
from datetime import datetime

STATS_FILE = "stats.json"
HISTORY_FILE = "history.json"

def make_deposit():
    try:
        # Pobieranie kwoty z argumentu (np. z GitHub Actions)
        amount = float(sys.argv[1])
    except:
        print("❌ Błąd: Nie podano poprawnej kwoty.")
        return

    now = datetime.now()
    date_str = now.strftime("%d.%m.%Y %H:%M")

    # --- 1. DOPISANIE DO HISTORII ---
    history = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)

    deposit_entry = {
        "id": f"DEP-{int(now.timestamp())}",
        "home": "📥 DEPOZYT",
        "away": "Wpłata własna",
        "profit": amount, 
        "stake": 0,
        "odds": 1.0,
        "sport": "FINANCE",
        "status": "DEPOSIT", # Zmienione na DEPOSIT, aby settle.py mógł to odfiltrować
        "time": now.isoformat()
    }
    history.append(deposit_entry)

    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=4, ensure_ascii=False)

    # --- 2. AKTUALIZACJA STATS.JSON ---
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, "r", encoding="utf-8") as f:
            stats = json.load(f)
        
        # AKTUALIZACJA: Zwiększamy Bankroll, ale NIE ruszamy "zysk_total"
        current_bankroll = stats.get("bankroll", 0)
        stats["bankroll"] = round(current_bankroll + amount, 2)
        stats["last_sync"] = date_str

        with open(STATS_FILE, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=4, ensure_ascii=False)
        
        print(f"✅ Sukces: {amount} PLN dodane do Bankrolla.")
        print(f"💰 Nowy bankroll: {stats['bankroll']} PLN (Zysk Total bez zmian).")
    else:
        print("⚠️ Uwaga: Plik stats.json nie istnieje, zaktualizowano tylko historię.")

if __name__ == "__main__":
    make_deposit()
