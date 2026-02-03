import json
import os
from datetime import datetime, timezone

HISTORY_FILE = "history.json"

def add_withdrawal(amount, note="Wypłata"):
    if not os.path.exists(HISTORY_FILE):
        print("❌ Brak pliku historii!")
        return
    
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        history = json.load(f)
    
    # Tworzymy wpis o wypłacie
    entry = {
        "id": f"wd-{int(datetime.now().timestamp())}",
        "home": "🏦 WYPŁATA",
        "away": note,
        "sport": "FINANCE",
        "outcome": "CASH_OUT",
        "odds": 1.0,
        "stake": 0,
        "profit": -float(amount),  # Wartość ujemna odejmuje się od zysku
        "status": "WITHDRAW",
        "score": "0:0",
        "time": datetime.now(timezone.utc).isoformat()
    }
    
    history.append(entry)
    
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=4)
    
    print(f"✅ Pomyślnie zarejestrowano wypłatę: {amount} PLN")

if __name__ == "__main__":
    # Możesz tu wpisać kwotę ręcznie przed uruchomieniem
    amount_to_withdraw = 1000 
    add_withdrawal(amount_to_withdraw)
