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
    """Generuje plik stats.json z nazwami kluczy pasującymi do Twojego HTML"""
    
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
            # Obsługa formatu czasu z Z lub +00:00
            m_time_str = m.get('time', '').replace("Z", "+00:00")
            m_time = datetime.fromisoformat(m_time_str)
            if now - m_time < timedelta(hours=24):
                profit_24h += m.get('profit', 0)
        except: continue

    # MAPOWANIE KLUCZY DLA TWOJEGO HTML
    stats_data = {
        "bankroll": round(bankroll, 2),
        "zysk_total": round(total_profit, 2), # Pasuje do: s.zysk_total
        "zysk_24h": round(profit_24h, 2),     # Pasuje do: s.zysk_24h
        "roi": round(bankroll, 0),            # Twój HTML używa s.roi do wyświetlania Bankrollu
        "yield": round(yield_val, 2),         # Pasuje do: s.yield
        "obrot": len(history),                # Pasuje do: s.obrot
        "upcoming_val": active_count,         # Pasuje do: s.upcoming_val
        "total_bets_count": len(history),     # Pasuje do: s.total_bets_count
        "last_sync": datetime.now().strftime("%H:%M:%S"), # Pasuje do: s.last_sync
        "wykres": chart_points,               # Pasuje do: s.wykres (funkcja renderHistory)
        "skutecznosc": round(accuracy, 1),    # Pasuje do: s.skutecznosc
        "history_preview": history[-15:]
    }
    
    with open(STATS_JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(stats_data, f, indent=4)
    print(f"✅ Strona WWW zsynchronizowana. Bankroll: {round(bankroll, 2)}")

def send_telegram_results(message):
    token = get_secret("T_TOKEN")
    chat = get_secret("T_CHAT_RESULTS") or get_secret("T_CHAT")
    if not token or not chat: return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat, "text": message, "parse_mode": "HTML"}
    try: requests.post(url, json=payload, timeout=15)
    except: pass

def generate_report(history, active_count):
    total_profit = sum(m.get('profit', 0) for m in history)
    base_capital = 5000 
    bankroll = base_capital + total_profit
    
    wins = sum(1 for m in history if m.get('status') == 'WIN')
    losses = sum(1 for m in history if m.get('status') == 'LOSS')
    total_matches = wins + losses
    
    accuracy = (wins / total_matches * 100) if total_matches > 0 else 0
    total_staked = sum(m.get('stake', 0) for m in history if m.get('status') in ['WIN', 'LOSS'])
    yield_val = (total_profit / total_staked * 100) if total_staked > 0 else 0

    # Wysyłka Telegram (Results)
    report = [
        "📊 <b>STATYSTYKI</b>",
        f"🏦 <b>BANKROLL:</b> {round(bankroll, 2)} PLN",
        f"💰 Zysk Total: {round(total_profit, 2)} PLN",
        f"🎯 Skuteczność: {round(accuracy, 1)}% | Yield: {round(yield_val, 2)}%",
        f"⏳ W grze: {active_count}",
        "━━━━━━━━━━━━━━━"
    ]
    send_telegram_results("\n".join(report))
    
    # Aktualizacja pliku dla strony WWW
    update_web_stats(history, bankroll, total_profit, accuracy, yield_val, active_count)

def settle_matches():
    # Pobieranie kluczy
    api_keys = [get_secret(f"ODDS_KEY_{i}" if i > 1 else "ODDS_KEY") for i in range(1, 11) if get_secret(f"ODDS_KEY_{i}" if i > 1 else "ODDS_KEY")]
    
    # Dane wejściowe
    active_coupons = []
    if os.path.exists(COUPONS_FILE):
        with open(COUPONS_FILE, "r", encoding="utf-8") as f: active_coupons = json.load(f)

    history = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f: history = json.load(f)

    # --- TUTAJ POWINNA BYĆ TWOJA LOGIKA SPRAWDZANIA WYNIKÓW (API) ---
    # Jeśli chcesz, bym ją tu dopisał, daj znać. 
    # Na razie zostawiam puste, aby nie nadpisać Twojej metody sprawdzania.

    # Finalizacja: Telegram + WWW
    generate_report(history, len(active_coupons))

if __name__ == "__main__":
    settle_matches()
