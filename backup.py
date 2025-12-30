import os
import requests
import zipfile
from datetime import datetime

def send_full_backup():
    token = os.getenv("T_TOKEN")
    chat = os.getenv("T_CHAT")
    zip_name = "full_bot_backup.zip"

    # Tworzenie archiwum ZIP ze wszystkimi ważnymi plikami
    with zipfile.ZipFile(zip_name, 'w') as zipf:
        for root, dirs, files in os.walk('.'):
            for file in files:
                # Pakujemy tylko skrypty, bazę i konfigurację (omijamy ukryte foldery gita)
                if file.endswith(('.py', '.json', '.yml')) and '.git' not in root:
                    zipf.write(os.path.join(root, file))

    date_str = datetime.now().strftime("%d.%m.%Y")
    url = f"https://api.telegram.org/bot{token}/sendDocument"
    
    try:
        with open(zip_name, "rb") as f:
            requests.post(url, 
                         data={"chat_id": chat, "caption": f"🗄 PEŁNY BACKUP PROJEKTU: {date_str}"},
                         files={"document": f})
        os.remove(zip_name) # Usuń plik po wysłaniu
        print("Pełny backup wysłany.")
    except Exception as e:
        print(f"Błąd: {e}")

if __name__ == "__main__":
    send_full_backup()
