import json
import os
import requests
from datetime import datetime, timezone

HISTORY_FILE = "history.json"
STATS_FILE = "stats.json"

def send_telegram(message):
    token = os.getenv("T_TOKEN")
    chat = os.getenv("T_CHAT")
    if not token or not chat:
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print("Telegram error:", e)

def add_withdraw(amount, note="Wypłata pieniędzy"):
    amount = float(amount)
    
    # --- CZĘŚĆ 1: AKTUALIZACJA HISTORY.JSON ---
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)
        
        entry = {
            "id": f"wd-{int(datetime.now().timestamp())}",
            "home": "🏦 WYPŁATA",
            "away": note,
            "sport": "FINANCE",
            "outcome": "WITHDRAW",
            "odds": 1.0,
            "stake": 0,
            "profit": -amount,
            "status": "WITHDRAW",
            "score": "0:0",
            "time": datetime.now(timezone.utc).isoformat(),
            "type": "WITHDRAW"
        }
        history.append(entry)
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=4, ensure_ascii=False)

    # --- CZĘŚĆ 2: AKTUALIZACJA STATS.JSON (Aby bankroll spadł na stronie) ---
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, "r", encoding="utf-8") as f:
            stats = json.load(f)
        
        # Odejmowanie od bankrolla
        stats["bankroll"] = stats.get("bankroll", 0) - amount
        # Aktualizacja daty synchronizacji
        stats["last_sync"] = datetime.now().strftime("%d.%m.%Y %H:%M")

        with open(STATS_FILE, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=4, ensure_ascii=False)

    # --- CZĘŚĆ 3: TELEGRAM ---
    msg = (
        "🏦 <b>WYPŁATA PIENIĘDZY</b>\n\n"
        f"💸 Kwota: <b>-{amount:.2f} PLN</b>\n"
        f"🕒 Data: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
        "📊 Bankroll na stronie został zaktualizowany"
    )
    send_telegram(msg)
    print(f"✅ Zarejestrowano wypłatę: -{amount:.2f} PLN")

if __name__ == "__main__":
    # Obsługa ręcznego wpisania kwoty (jeśli nie przez GitHub Actions)
    import sys
    if len(sys.argv) > 1:
        add_withdraw(sys.argv[1])
    else:
        try:
            val = input("Podaj kwotę wypłaty: ")
            add_withdraw(val)
        except EOFError:
            pass
