import json
import os
import sys
from datetime import datetime

STATS_FILE = "stats.json"
HISTORY_FILE = "history.json"

def make_deposit():
    try:
        # Pobieranie kwoty z argumentu (z GitHub Actions)
        amount = float(sys.argv[1])
    except:
        print("Błąd: Nie podano poprawnej kwoty.")
        return

    now = datetime.now()
    date_str = now.strftime("%d.%m.%Y %H:%M")

    # --- 1. DOPISANIE DO HISTORII ---
    history = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)

    deposit_entry = {
        "home": "📥 DEPOZYT",
        "away": "Wpłata własna",
        "profit": amount, # Kwota dodatnia
        "stake": 0,
        "odds": 0,
        "sport": "FINANCE",
        "status": "DEPOSIT",
        "time": now.isoformat()
    }
    history.append(deposit_entry)

    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=4, ensure_ascii=False)

    # --- 2. AKTUALIZACJA STATS.JSON ---
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, "r", encoding="utf-8") as f:
            stats = json.load(f)
        
        # DODAJEMY do bankrolla
        stats["bankroll"] = round(stats.get("bankroll", 0) + amount, 2)
        stats["last_sync"] = date_str

        with open(STATS_FILE, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=4, ensure_ascii=False)

    print(f"✅ Wpłacono: {amount} PLN. Nowy bankroll: {stats['bankroll']} PLN")

if __name__ == "__main__":
    make_deposit()
