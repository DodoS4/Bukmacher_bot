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
    """Generuje plik stats.json z pełnymi danymi dla strony WWW"""
    # ZABEZPIECZENIE: Jeśli historia jest pusta, nie nadpisuj strony zerami
    if not history or total_profit == 0:
        print("⚠️ Ostrzeżenie: Wykryto zerowy zysk. Pomijam aktualizację stats.json, aby uniknąć błędów na stronie.")
        return

    stats_data = {
        "bankroll": round(bankroll, 2),
        "total_profit": round(total_profit, 2),
        "zysk_24h": 0, # Możesz tu dodać obliczenia dla 24h jeśli potrzebujesz
        "accuracy": round(accuracy, 1),
        "yield": round(yield_val, 2),
        "in_play": active_count,
        "last_update": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "history_preview": history[-15:]
    }
    
    with open(STATS_JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(stats_data, f, indent=4)
    print(f"✅ Strona zaktualizowana: Bankroll {round(bankroll, 2)} PLN")

def send_telegram_results(message):
    token = get_secret("T_TOKEN")
    chat = get_secret("T_CHAT_RESULTS") or get_secret("T_CHAT")
    if not token or not chat: return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat, "text": message, "parse_mode": "HTML"}
    try: requests.post(url, json=payload, timeout=15)
    except: pass

def generate_report(history, active_count):
    # Liczymy zysk sumując wszystko z history.json
    total_profit = sum(m.get('profit', 0) for m in history)
    base_capital = 5000 
    bankroll = base_capital + total_profit
    
    wins = sum(1 for m in history if m.get('status') == 'WIN')
    losses = sum(1 for m in history if m.get('status') == 'LOSS')
    total_matches = wins + losses
    
    accuracy = (wins / total_matches * 100) if total_matches > 0 else 0
    total_staked = sum(m.get('stake', 0) for m in history if m.get('status') in ['WIN', 'LOSS'])
    yield_val = (total_profit / total_staked * 100) if total_staked > 0 else 15.18 # Twoja stała wartość jeśli stake=0

    # 1. Raport Telegram
    report = [
        "📊 <b>STATYSTYKI</b>",
        f"🏦 <b>BANKROLL:</b> {round(bankroll, 2)} PLN",
        f"💰 Zysk Total: {round(total_profit, 2)} PLN",
        f"🎯 Skuteczność: {round(accuracy, 1)}% | Yield: {round(yield_val, 2)}%",
        f"⏳ W grze: {active_count}",
        "━━━━━━━━━━━━━━━"
    ]
    
    send_telegram_results("\n".join(report))
    
    # 2. Aktualizacja WWW (Z zabezpieczeniem)
    update_web_stats(history, bankroll, total_profit, accuracy, yield_val, active_count)

def settle_matches():
    api_keys = [get_secret(f"ODDS_KEY_{i}" if i > 1 else "ODDS_KEY") for i in range(1, 11) if get_secret(f"ODDS_KEY_{i}" if i > 1 else "ODDS_KEY")]
    
    # Wczytaj kupony
    active_coupons = []
    if os.path.exists(COUPONS_FILE):
        with open(COUPONS_FILE, "r", encoding="utf-8") as f: active_coupons = json.load(f)

    # Wczytaj historię
    history = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f: history = json.load(f)

    # ... (tutaj Twoja logika sprawdzania wyników w API) ...
    # Zakładamy, że sprawdzasz wyniki i aktualizujesz listę history

    # NA KONIEC: ZAWSZE wyślij raport i odśwież stronę WWW
    generate_report(history, len(active_coupons))

if __name__ == "__main__":
    settle_matches()
