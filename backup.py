import os
import requests
from datetime import datetime

def send_backup():
    token = os.getenv("T_TOKEN")
    chat = os.getenv("T_CHAT")
    file_path = "coupons.json"

    if not os.path.exists(file_path):
        print("Brak pliku do backupu.")
        return

    date_str = datetime.now().strftime("%d.%m.%Y")
    url = f"https://api.telegram.org/bot{token}/sendDocument"
    
    try:
        with open(file_path, "rb") as f:
            requests.post(url, 
                         data={"chat_id": chat, "caption": f"📦 BACKUP BAZY: {date_str}"},
                         files={"document": f})
        print("Backup wysłany pomyślnie.")
    except Exception as e:
        print(f"Błąd backupu: {e}")

if __name__ == "__main__":
    send_backup()
