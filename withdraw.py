import json
import os
import requests
from datetime import datetime, timezone

HISTORY_FILE = "history.json"

def send_telegram(message):
    token = os.getenv("T_TOKEN")
    chat = os.getenv("T_CHAT")
    if not token or not chat:
        print("⚠️ Brak danych Telegram")
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
        print("⚠️ Błąd Telegram:", e)

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

    with open(HISTOR
