import json
import os
from datetime import datetime

def soft_reset():
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    new_start_balance = 1000.0

    # 1. Aktualizujemy stats.json - to zmieni licznik na stronie
    new_stats = {
        "bankroll": new_start_balance,
        "zysk_total": 0.0,    # Resetujemy zysk wizualny, by liczyć od nowa
        "zysk_24h": 0.0,
        "obrot": 0.0,
        "yield": 0.0,
        "last_sync": now,
        "upcoming_val": 0,
        "history_graph": [new_start_balance]
    }

    with open("stats.json", "w", encoding="utf-8") as f:
        json.dump(new_stats, f, indent=4)

    # 2. Oznaczamy stare mecze w historii jako "ARCHIVE" 
    # Dzięki temu zostaną w pliku (bot je widzi), ale Dashboard może je ignorować
    if os.path.exists("history.json"):
        with open("history.json", "r", encoding="utf-8") as f:
            history = json.load(f)
        
        for m in history:
            if m.get("status") != "ARCHIVED":
                m["status"] = "ARCHIVED" # Archiwizujemy stare wyniki finansowe

        with open("history.json", "w", encoding="utf-8") as f:
            json.dump(history, f, indent=4)

    print(f"✅ Miękki reset zakończony. Bankroll: {new_start_balance} PLN. Historia zachowana.")

if __name__ == "__main__":
    soft_reset()
