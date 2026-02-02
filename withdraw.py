import json
import os
import requests
from datetime import datetime, timezone

HISTORY_FILE = "history.json"


def send_telegram(message):
    token = os.getenv("T_TOKEN")
    chat = os.getenv("T_CHAT")

    if not token or not chat:
        print("⚠️ Brak danych Telegram (T_TOKEN / T_CHAT)")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat,
        "text": message,
        "parse_mode": "HTML"
    }

    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print("⚠️ Błąd wysyłania Telegram:", e)


def add_withdraw(amount, note="Wypłata pieniędzy"):
    if not os.path.exists(HISTORY_FILE):
        print("❌ Brak pliku history.json")
        return

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
        "profit": -float(amount),   # odejmuje od bankrolla
        "status": "WITHDRAW",
        "score": "0:0",
        "time": datetime.now(timezone.utc).isoformat(),
        "type": "WITHDRAW"
    }

    history.append(entry)

    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=4, ensure_ascii=False)

    msg = (
        "🏦 <b>WYPŁATA PIENIĘDZY</b>\n\n"
        f"💸 Kwota: <b>-{amount:.2f} PLN</b>\n"
        f"🕒 Data: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
        "📊 Bankroll został zaktualizowany"
    )

    send_telegram(msg)
    print(f"✅ Zarejestrowano wypłatę: -{amount:.2f} PLN")


if __name__ == "__main__":
    # test lokalny
    add_withdraw(1000)
