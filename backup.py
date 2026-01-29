import os
import requests
import zipfile
from datetime import datetime

def send_full_backup():
    token = os.getenv("T_TOKEN")
    chat = os.getenv("T_CHAT")
    zip_name = "full_bot_backup.zip"

    with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # 1. Pakujemy wszystkie pliki z głównego folderu
        for root, dirs, files in os.walk('.'):
            # Wykluczamy ciężkie/niepotrzebne foldery
            if any(x in root for x in ['.git', 'venv', '__pycache__']):
                continue
                
            for file in files:
                if file.endswith(('.py', '.json', '.yml', '.yaml', '.txt')):
                    if file != zip_name:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, '.')
                        zipf.write(file_path, arcname)
                        print(f"📦 Dodano: {arcname}")

        # 2. WYMUSZONE DODANIE WORKFLOWS (jeśli os.walk je pominął)
        workflow_path = ".github/workflows"
        if os.path.exists(workflow_path):
            for file in os.listdir(workflow_path):
                if file.endswith(('.yml', '.yaml')):
                    file_path = os.path.join(workflow_path, file)
                    arcname = os.path.join(".github", "workflows", file)
                    # Sprawdzamy czy pliku już nie ma w ZIP, żeby nie dublować
                    if arcname not in zipf.namelist():
                        zipf.write(file_path, arcname)
                        print(f"📦 Wymuszono dodanie: {arcname}")

    date_str = datetime.now().strftime("%d.%m.%Y %H:%M")
    url = f"https://api.telegram.org/bot{token}/sendDocument"
    
    try:
        with open(zip_name, "rb") as f:
            requests.post(url, 
                         data={"chat_id": chat, "caption": f"🗄 FULL BACKUP (Scripts + YAMLs): {date_str}"},
                         files={"document": f},
                         timeout=30)
        os.remove(zip_name)
        print("✅ Backup wysłany.")
    except Exception as e:
        print(f"❌ Błąd: {e}")

if __name__ == "__main__":
    send_full_backup()
