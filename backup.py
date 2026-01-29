import os
import requests
import zipfile
from datetime import datetime

def send_full_backup():
    token = os.getenv("T_TOKEN")
    chat = os.getenv("T_CHAT")
    zip_name = "bot_backup.zip"

    # Foldery i pliki do zignorowania
    ignored_items = {'.git', '__pycache__', 'venv', '.github'}

    with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk('.'):
            # Filtrowanie folderów
            dirs[:] = [d for d in dirs if d not in ignored_items]
            
            for file in files:
                # Pakujemy tylko istotne formaty
                if file.endswith(('.py', '.json', '.yml', '.txt')):
                    if file != zip_name: # Nie pakuj samego siebie
                        file_path = os.path.join(root, file)
                        # Zapisujemy w ZIP bez zbędnych ścieżek nadrzędnych
                        zipf.write(file_path, os.path.relpath(file_path, '.'))

    date_str = datetime.now().strftime("%d.%m.%Y %H:%M")
    url = f"https://api.telegram.org/bot{token}/sendDocument"
    
    try:
        with open(zip_name, "rb") as f:
            r = requests.post(url, 
                             data={"chat_id": chat, "caption": f"🗄 BACKUP: {date_str}"},
                             files={"document": f},
                             timeout=30)
            if r.status_code == 200:
                print("✅ Backup wysłany pomyślnie.")
            else:
                print(f"❌ Błąd Telegrama: {r.text}")
        
        os.remove(zip_name)
    except Exception as e:
        print(f"❌ Błąd podczas wysyłki: {e}")

if __name__ == "__main__":
    send_full_backup()
