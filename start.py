import requests
import os
from datetime import datetime

# ====== KONFIGURACJA ======
T_TOKEN = os.getenv("T_TOKEN")        # token bota
T_CHAT = os.getenv("T_CHAT")          # ID kanału / grupy

# ====== FUNKCJA WYSYŁKI ======
def send_msg(text):
    if not T_TOKEN or not T_CHAT:
        print("❌ Brak T_TOKEN lub T_CHAT")
        return

    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
    payload = {
        "chat_id": T_CHAT,
        "text": text,
        "parse_mode": "Markdown"
    }

    try:
        r = requests.post(url, json=payload, timeout=15)
        print("Status:", r.status_code)
        print("Odpowiedź:", r.text)
    except Exception as e:
        print("❌ Błąd:", e)

# ====== START ======
if __name__ == "__main__":
    send_msg(
        "🤖 *TEST BOTA*\n"
        "━━━━━━━━━━━━━━\n"
        f"🕒 Czas: `{datetime.now()}`\n"
        "✅ Jeśli to widzisz – bot działa!"
    )
