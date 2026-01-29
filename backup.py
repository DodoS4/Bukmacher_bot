import os
import requests
import zipfile
from datetime import datetime

def send_full_backup():
    token = os.getenv("T_TOKEN")
    chat = os.getenv("T_CHAT")
    zip_name = "full_bot_backup.zip"

    with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk('.'):
            # Omijamy tylko folder .git (jest bardzo ciężki i zbędny)
            if '.git' in root:
                continue
                
            for file in files:
                # Interesują nas skrypty, dane oraz pliki konfiguracyjne YAML
                if file.endswith(('.py', '.json', '.yml', '.yaml', '.txt')):
                    if file != zip_name:
                        file_path = os.path.join(root, file)
                        # Zachowujemy strukturę folderów (np. .github/workflows/...)
                        arcname = os.path.relpath(file_path, '.')
                        zipf.write(file_path, arcname)

    date_str = datetime.now().strftime("%d.%m.%Y %H:%M")
    url = f"https://api.telegram.org/bot{token}/sendDocument"
    
    try:
        with open(zip_name, "rb") as f:
            r = requests.post(url, 
                             data={"chat_id": chat, "caption": f"🗄 PEŁNY BACKUP (W tym Workflows): {date_str}"},
                             files={"document": f},
                             timeout=30)
            if r.status_code == 200:
                print("✅ Backup wysłany pomyślnie.")
            else:
                print(f"❌ Błąd Telegrama: {r.status_code}")
        
        os.remove(zip_name)
    except Exception as e:
        print(f"❌ Błąd: {e}")

if __name__ == "__main__":
    send_full_backup()
