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

    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)
    except Exception as e:
        print(f"Błąd podczas wczytywania JSON: {e}")
        return

    if not history:
        print("Historia jest pusta.")
        return

    # --- BEZPIECZNE OBLICZENIA (zabezpieczenie przed KeyError) ---
    # Liczymy tylko rozliczone typy (WIN/LOSS), pomijamy te bez statusu
    settled_bets = [item for item in history if item.get('status') in ["WIN", "LOSS"]]
    
    total_types = len(settled_bets)
    wins = sum(1 for item in settled_bets if item.get('status') == "WIN")
    win_rate = (wins / total_types * 100) if total_types > 0 else 0
    
    total_profit = sum(item.get('profit', 0) for item in settled_bets)
    total_turnover = sum(item.get('stake', 0) for item in settled_bets)
    
    # --- SEKCJA PODATKOWA ---
    # Podatek 12% od każdej postawionej złotówki (od obrotu)
    total_tax_paid = total_turnover * 0.12
    # Zysk bez podatku (co by było gdyby...)
    profit_without_tax = total_profit + total_tax_paid
    
    # Yieldy
    current_yield = (total_profit / total_turnover * 100) if total_turnover > 0 else 0
    algo_yield = (profit_without_tax / total_turnover * 100) if total_turnover > 0 else 0

    # --- OBLICZENIA 24H ---
    now = datetime.now()
    yesterday = now - timedelta(days=1)
    last_24h_profit = 0
    
    for item in settled_bets:
        try:
            # Próba odczytu daty - dostosuj format jeśli Twój JSON używa innego
            # Przyjmujemy ISO format (np. 2024-05-20T12:00:00)
            item_date_str = item.get('date') or item.get('time')
            if item_date_str:
                # Uproszczone sprawdzenie daty (pobiera pierwsze 10 znaków RRRR-MM-DD)
                item_date = datetime.strptime(item_date_str[:10], "%Y-%m-%d")
                if item_date >= yesterday:
                    last_24h_profit += item.get('profit', 0)
        except:
            continue

    # --- WIADOMOŚĆ ---
    emoji = "💰" if total_profit >= 0 else "📉"
    
    msg = (
        f"📊 <b>PEŁNE STATYSTYKI BOTA</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"{emoji} Zysk Netto: <b>{total_profit:.2f} PLN</b>\n"
        f"🏛 Oddany Podatek: <b>{total_tax_paid:.2f} PLN</b>\n"
        f"🚀 Zysk BEZ podatku: <b>{profit_without_tax:.2f} PLN</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🔄 Obrót: <b>{total_turnover:.2f} PLN</b>\n"
        f"📈 Realny Yield: <b>{current_yield:.2f}%</b>\n"
        f"🧠 Algo Yield: <b>{algo_yield:.2f}%</b>\n"
        f"✅ Typy / WR%: <b>{total_types} / {win_rate:.1f}%</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🕒 Ostatnie 24h: <b>{last_24h_profit:.2f} PLN</b>\n"
        f"📅 <i>Stan na: {now.strftime('%d.%m.%Y %H:%M')}</i>"
    )

    # --- WYSYŁKA ---
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}
    
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code == 200:
            print("✅ Statystyki wysłane.")
        else:
            print(f"❌ Błąd Telegrama: {r.text}")
    except Exception as e:
        print(f"❌ Błąd wysyłki: {e}")

if __name__ == "__main__":
    generate_stats()
