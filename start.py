# ================= KOMUNIKACJA =================

def send_msg(text):
    if not T_TOKEN or not T_CHAT:
        print("BŁĄD: Brak T_TOKEN lub T_CHAT w środowisku (Secrets)!")
        return
    
    # Poprawny URL dla API Telegrama
    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
    
    payload = {
        "chat_id": T_CHAT,
        "text": text,
        "parse_mode": "Markdown"
    }
    
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code != 200:
            print(f"Błąd Telegrama (Status {r.status_code}): {r.text}")
        else:
            print("Wiadomość wysłana pomyślnie!")
    except Exception as e:
        print(f"Wyjątek przy wysyłce do Telegrama: {e}")

# ================= URUCHOMIENIE =================

if __name__ == "__main__":
    print("Inicjalizacja bota...")
    
    # Informacja testowa - wyśle się przy każdym uruchomieniu na GitHub Actions
    current_time = datetime.now().strftime("%H:%M:%S")
    send_msg(f"🤖 **Bot uruchomiony poprawnie!**\nGodzina: `{current_time}`\nStatus: `Szukam okazji...`")
    
    try:
        run()
        print("Skanowanie zakończone.")
    except Exception as e:
        error_msg = f"❌ **Błąd krytyczny bota:**\n`{str(e)}`"
        print(error_msg)
        send_msg(error_msg)
