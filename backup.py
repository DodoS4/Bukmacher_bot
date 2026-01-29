import os
import requests
import zipfile
from datetime import datetime

def send_full_backup():
    token = os.getenv("T_TOKEN")
    chat = os.getenv("T_CHAT")
    zip_name = "full_bot_backup.zip"

    # Tworzenie ZIP
    with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # Przeszukujemy cały katalog główny projektu
        for root, dirs, files in os.walk('.'):
            # Ignorujemy tylko folder .git, bo jest za duży
            if '.git' in root:
                continue
            
            for file in files:
                # Szukamy skryptów, danych i plików workflow (.yml)
                if file.endswith(('.py', '.json', '.yml', '.yaml', '.txt')):
                    file_path = os.path.join(root, file)
                    
                    # Tworzymy ścieżkę wewnątrz ZIP (zachowuje foldery np. .github/workflows)
                    arcname = os.path.relpath(file_path, '.')
                    
                    zipf.write(file_path, arcname)
                    print(f"📦 Spakowano: {arcname}")

    date_str = datetime.now().strftime("%d.%m.%Y %H:%M")
    url = f"https://api.telegram.org/bot{token}/sendDocument"
    
    try:
        with open(zip_name, "rb") as f:
            r = requests.post(
                url, 
                data={"chat_id": chat, "caption": f"🗄 PEŁNY BACKUP: {date_str}\n(Zawiera pliki YAML i skrypty)"},
                files={"document": f},
                timeout=30
            )
            if r.status_code == 200:
                print("✅ Backup wysłany na Telegram.")
            else:
                print(f"❌ Błąd Telegrama: {r.status_code} - {r.text}")
        
        os.remove(zip_name)
    except Exception as e:
        print(f"❌ Błąd krytyczny: {e}")

if __name__ == "__main__":
    send_full_backup()
