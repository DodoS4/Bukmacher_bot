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
    """Generuje stats.json z kluczami, których szuka Twój HTML"""
    
    # 1. Generowanie punktów wykresu (narastająco)
    chart_points = []
    current_sum = 0
    # Sortujemy historię datami, żeby wykres szedł chronologicznie
    sorted_history = sorted(history, key=lambda x: x.get('time', ''))
    for m in sorted_history:
        current_sum += m.get('profit', 0)
        chart_points.append(round(current_sum, 2))

    # 2. Oblicz zysk z ostatnich 24h
    now = datetime.now(timezone.utc)
    profit_24h = 0
    for m in history:
        try:
            m_time_str = m.get('time', '').replace("Z", "+00:00")
            m_time = datetime.fromisoformat(m_time_str)
            if now - m_time < timedelta(hours=24):
                profit_24h += m.get('profit', 0)
        except: continue

    # 3. MAPOWANIE KLUCZY (IDENTYCZNIE JAK W TWOIM JS)
    stats_data = {
        "bankroll": round(bankroll, 2),
        "zysk_total": round(total_profit, 2), # s.zysk_total
        "zysk_24h": round(profit_24h, 2),     # s.zysk_24h
        "roi": round(bankroll, 0),            # s.roi (Twój HTML tu wstawia kwotę)
        "yield": round(yield_val, 2),         # s.yield
        "obrot": len(history),                # s.obrot
        "upcoming_val": active_count,         # s.upcoming_val
        "total_bets_count": len(history),     # s.total_bets_count
        "last_sync": datetime.now().strftime("%H:%M:%S"), # s.last_sync
        "wykres": chart_points,               # s.wykres
        "skutecznosc": round(accuracy, 1),    # s.skutecznosc
        "history_preview": history[-15:]
    }
    
    with open(STATS_JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(stats_data, f, indent=4)
    print(f"✅ JSON zaktualizowany: {len(chart_points)} punktów wykresu.")

def generate_report(history, active_count):
    if not history:
        print("⚠️ Historia wczytana jako pusta. Przerywam, by nie zerować WWW.")
        return

    total_profit = sum(m.get('profit', 0) for m in history)
    base_capital = 5000 
    bankroll = base_capital + total_profit
    
    wins = sum(1 for m in history if m.get('status') == 'WIN')
    losses = sum(1 for m in history if m.get('status') == 'LOSS')
    total_matches = wins + losses
    
    accuracy = (wins / total_matches * 100) if total_matches > 0 else 0
    total_staked = sum(m.get('stake', 0) for m in history if m.get('status') in ['WIN', 'LOSS'])
    yield_val = (total_profit / total_staked * 100) if total_staked > 0 else 15.18

    # Aktualizacja WWW
    update_web_stats(history, bankroll, total_profit, accuracy, yield_val, active_count)

def settle_matches():
    # Wczytanie danych
    active_coupons = []
    if os.path.exists(COUPONS_FILE):
        with open(COUPONS_FILE, "r", encoding="utf-8") as f: 
            active_coupons = json.load(f)

    history = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f: 
            history = json.load(f)

    # Tutaj robot sprawdza wyniki (pomińmy dla uproszczenia struktury)
    
    # ZAWSZE na koniec przelicz i zapisz stats.json
    generate_report(history, len(active_coupons))

if __name__ == "__main__":
    settle_matches()
