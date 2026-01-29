import json
import os
import requests
from datetime import datetime, timedelta

# --- KONFIGURACJA ---
HISTORY_FILE = "history.json"
TOKEN = os.getenv("T_TOKEN")
CHAT_ID = os.getenv("T_CHAT")

def generate_stats():
    if not os.path.exists(HISTORY_FILE):
        print("Brak pliku historii.")
        return

    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        history = json.load(f)

    if not history:
        print("Historia jest pusta.")
        return

    # Obliczenia ogólne
    total_types = len(history)
    wins = sum(1 for item in history if item['status'] == "WIN")
    win_rate = (wins / total_types * 100) if total_types > 0 else 0
    
    total_profit = sum(item['profit'] for item in history)
    total_turnover = sum(item['stake'] for item in history)
    
    # --- SEKCJA PODATKOWA ---
    # W Polsce podatek 12% płacony jest od każdej postawionej złotówki (od obrotu)
    total_tax_paid = total_turnover * 0.12
    # Zysk, który miałbyś w portfelu, gdybyś grał bez podatku (np. zagranicą)
    profit_without_tax = total_profit + total_tax_paid
    # Realny yield z uwzględnieniem podatku
    current_yield = (total_profit / total_turnover * 100) if total_turnover > 0 else 0
    # Yield, jaki wypracowuje Twój algorytm przed opodatkowaniem
    algo_yield = (profit_without_tax / total_turnover * 100) if total_turnover > 0 else 0

    # Statystyki z ostatnich 24h
    now = datetime.now()
    yesterday = now - timedelta(days=1)
    
    # Zakładamy, że w history.json czas jest w formacie ISO lub podobnym
    last_24h_profit = 0
    for item in history:
        try:
            # Próba dopasowania formatu daty (zależnie od tego jak zapisuje settle.py)
            item_time = datetime.fromisoformat(item['time'].replace('Z', '+00:00'))
            if item_time > yesterday.astimezone():
                last_24h_profit += item['profit']
        except:
            continue

    # --- BUDOWANIE WIADOMOŚCI ---
    emoji_profit = "💰" if total_profit >= 0 else "📉"
    
    msg = (
        f"📊 <b>OFICJALNE STATYSTYKI BOTA</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"{emoji_profit} Zysk Netto: <b>{total_profit:.2f} PLN</b>\n"
        f"🏛 Oddany Podatek: <b>{total_tax_paid:.2f} PLN</b>\n"
        f"🚀 Zysk bez podatku: <b>{profit_without_tax:.2f} PLN</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"💸 Zysk 24h: <b>{last_24h_profit:.2f} PLN</b>\n"
        f"🔄 Obrót: <b>{total_turnover:.2f} PLN</b>\n"
        f"📈 Realny Yield: <b>{current_yield:.2f}%</b>\n"
        f"🧠 Algo Yield: <b>{algo_yield:.2f}%</b>\n"
        f"✅ Typy / WR%: <b>{total_types} / {win_rate:.1f}%</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📅 Generowano: {now.strftime('%d.%m | %H:%M')}"
    )

    # Wysyłka na Telegram
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": msg,
        "parse_mode": "HTML"
    }
    
    try:
        r = requests.post(url, json=payload)
        if r.status_code == 200:
            print("Statystyki wysłane pomyślnie.")
        else:
            print(f"Błąd Telegrama: {r.text}")
    except Exception as e:
        print(f"Błąd wysyłki: {e}")

if __name__ == "__main__":
    generate_stats()
