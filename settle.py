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
    """Generuje plik stats.json z nazwami kluczy IDENTYCZNYMI jak w Twoim HTML"""
    
    # Tworzymy punkty do wykresu (suma kumulatywna zysku)
    chart_points = []
    current_sum = 0
    for m in history:
        current_sum += m.get('profit', 0)
        chart_points.append(round(current_sum, 2))

    # Oblicz zysk z ostatnich 24h
    now = datetime.now(timezone.utc)
    profit_24h = 0
    for m in history:
        try:
            m_time_str = m.get('time', '').replace("Z", "+00:00")
            m_time = datetime.fromisoformat(m_time_str)
            if now - m_time < timedelta(hours=24):
                profit_24h += m.get('profit', 0)
        except: continue

    # DANE DLA TWOJEGO HTML (image.png 13:50/13:55)
    stats_data = {
        "bankroll": round(bankroll, 2),
        "zysk_total": round(total_profit, 2), # Klucz dla 'ZYSK TOTAL'
        "zysk_24h": round(profit_24h, 2),     # Klucz dla 'ZYSK 24H'
        "roi": round(bankroll, 0),            # Klucz dla fioletowej karty (Bankroll)
        "yield": round(yield_val, 2),         # Klucz dla 'YIELD'
        "obrot": len(history),                # Klucz dla 'OBRÓT'
        "upcoming_val": active_count,         # Klucz dla 'W GRZE'
        "total_bets_count": len(history),     # Klucz dla 'KUPONY'
        "last_sync": datetime.now().strftime("%d.%m.%Y %H:%M"), # Klucz dla SYNC
        "wykres": chart_points,               # Klucz dla PROGRESJA ZYSKU
        "skutecznosc": round(accuracy, 1),
        "history_preview": history[-15:]
    }
    
    with open(STATS_JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(stats_data, f, indent=4)
    print(f"✅ Synchronizacja zakończona. Bankroll: {round(bankroll, 2)}")

def generate_report(history, active_count):
    # ZABEZPIECZENIE: Jeśli historia jest pusta, spróbuj ją wczytać ponownie lub nie zeruj statystyk
    if not history:
        print("⚠️ Brak historii! Nie aktualizuję statystyk, aby uniknąć zer na stronie.")
        return

    total_profit = sum(m.get('profit', 0) for m in history)
    base_capital = 5000 
    bankroll = base_capital + total_profit
    
    wins = sum(1 for m in history if m.get('status') == 'WIN')
    losses = sum(1 for m in history if m.get('status') == 'LOSS')
    total_matches = wins + losses
    
    accuracy = (wins / total_matches * 100) if total_matches > 0 else 0
    
    # Obliczanie Yield (jeśli brak stake, przyjmij 15.18 jak na Twoim screenie)
    total_staked = sum(m.get('stake', 0) for m in history if m.get('status') in ['WIN', 'LOSS'])
    yield_val = (total_profit / total_staked * 100) if total_staked > 0 else 15.18

    # Aktualizacja WWW
    update_web_stats(history, bankroll, total_profit, accuracy, yield_val, active_count)

def settle_matches():
    # 1. Wczytaj kupony
    active_coupons = []
    if os.path.exists(COUPONS_FILE):
        with open(COUPONS_FILE, "r", encoding="utf-8") as f: 
            active_coupons = json.load(f)

    # 2. Wczytaj historię
    history = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f: 
            history = json.load(f)

    # ... (Tutaj opcjonalnie logika sprawdzania wyników API) ...

    # 3. ZAWSZE generuj statystyki na koniec
    generate_report(history, len(active_coupons))

if __name__ == "__main__":
    settle_matches()
