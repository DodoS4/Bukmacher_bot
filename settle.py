import os
import json
import requests
from datetime import datetime, timezone, timedelta

# --- KONFIGURACJA PLIKÓW ---
COUPONS_FILE = "coupons.json"
HISTORY_FILE = "history.json"
STATS_JSON_FILE = "stats.json"

def get_secret(name):
    val = os.environ.get(name) or os.getenv(name)
    return str(val).strip() if val else None

def update_web_stats(history, bankroll, total_profit, accuracy, yield_val, active_count):
    # 1. Generowanie wykresu
    chart_points = []
    current_sum = 0
    sorted_history = sorted(history, key=lambda x: x.get('time', ''))
    for m in sorted_history:
        current_sum += float(m.get('profit', 0))
        chart_points.append(round(current_sum, 2))

    # 2. Oblicz zysk 24h
    now = datetime.now(timezone.utc)
    profit_24h = 0
    for m in history:
        try:
            m_time = datetime.fromisoformat(m.get('time', '').replace("Z", "+00:00"))
            if now - m_time < timedelta(hours=24):
                profit_24h += float(m.get('profit', 0))
        except: continue

    # 3. DOKŁADNE MAPOWANIE POD TWÓJ HTML
    stats_data = {
        "bankroll": round(bankroll, 2),
        "zysk_total": round(total_profit, 2),
        "zysk_24h": round(profit_24h, 2),
        "roi": round(bankroll, 0), # Wyświetla Bankroll w fioletowej karcie
        "yield": round(yield_val, 2),
        "obrot": len(history),
        "upcoming_val": active_count,
        "total_bets_count": len(history),
        "last_sync": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "wykres": chart_points,
        "skutecznosc": round(accuracy, 1),
        "history_preview": history[-15:]
    }
    
    with open(STATS_JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(stats_data, f, indent=4)
    print("✅ Plik stats.json został zapisany pomyślnie.")

def settle_matches():
    # Wczytywanie plików z wymuszeniem kodowania UTF-8
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)
    except Exception as e:
        print(f"❌ Błąd wczytywania historii: {e}")
        return

    try:
        with open(COUPONS_FILE, "r", encoding="utf-8") as f:
            active_coupons = json.load(f)
    except:
        active_coupons = []

    if not history:
        print("⚠️ Historia jest pusta w pamięci skryptu!")
        return

    # Obliczenia
    total_profit = sum(float(m.get('profit', 0)) for m in history)
    base_capital = 5000 
    bankroll = base_capital + total_profit
    
    wins = sum(1 for m in history if m.get('status') == 'WIN')
    total_matches = sum(1 for m in history if m.get('status') in ['WIN', 'LOSS'])
    accuracy = (wins / total_matches * 100) if total_matches > 0 else 0
    
    total_staked = sum(float(m.get('stake', 0)) for m in history if m.get('status') in ['WIN', 'LOSS'])
    yield_val = (total_profit / total_staked * 100) if total_staked > 0 else 15.18

    # Aktualizacja
    update_web_stats(history, bankroll, total_profit, accuracy, yield_val, len(active_coupons))

if __name__ == "__main__":
    settle_matches()
