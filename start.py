import os
import requests

T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")

print("TOKEN OK:", bool(T_TOKEN))
print("CHAT_ID:", T_CHAT)

def send_msg(text):
    if not T_TOKEN or not T_CHAT:
        print("❌ Brak T_TOKEN lub T_CHAT")
        return

    r = requests.post(
        f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
        json={
            "chat_id": T_CHAT,
            "text": text
        },
        timeout=10
    )

    print("STATUS:", r.status_code)
    print("RESPONSE:", r.text)

send_msg("🧪 TEST: jeśli to widzisz, bot działa poprawnie")
