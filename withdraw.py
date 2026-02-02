import json
import os
from datetime import datetime, timezone
from urllib import request, parse

HISTORY_FILE = "history.json"

def send_telegram(message):
    token = os.getenv("T_TOKEN")
    chat = os.getenv("T_CHAT")
    if not token or not chat:
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = parse.urlencode({
        "chat_id": chat,
        "text": message,
        "parse_mode": "HTML"
    }).encode()

    try:
        req = request.Request(url, data=data)
        request.urlopen(req, timeout=10)
    except Exception as e:
        print("⚠️ Telegram error:", e)

def add_withdraw(amount, note="Wypłata"):
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
        "profit": -float(amount),
        "status": "WITHDRAW",
        "score": "—",
        "time": datetime.now(timezone.utc).isoformat(),
        "type": "WITHDRAW"
    }

    history.append(entry)

    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=4, ensure_ascii=False)

    msg = (
        "🏦 <b>WYPŁATA ZAREJESTROWANA</b>\n\n"
        f"💸 Kwota: <b>-{amount:.2f} PLN</b>\n"
        f"🕒 Data: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
        "📊 Bankroll został zaktualizowany"
    )

    send_telegram(msg)
    print(f"✅ Zarejestrowano wypłatę: -{amount} PLN")

if __name__ == "__main__":
    add_withdraw(1000)
