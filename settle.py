import os
import json
import requests
from datetime import datetime, timezone

# --- KONFIGURACJA PLIKÓW ---
COUPONS_FILE = "coupons.json"
HISTORY_FILE = "history.json"

# ================= PANCERNE POBIERANIE KLUCZY =================
def get_env_safe(name):
    """Pobiera zmienną środowiskową i czyści ją ze spacji."""
    val = os.environ.get(name) or os.getenv(name)
    return str(val).strip() if val and len(str(val).strip()) > 0 else None

def send_telegram_result(message):
    """Wysyła wynik rozliczenia na kanał wyników."""
    token = get_env_safe("T_TOKEN")
    # Próbuje wysłać na kanał wyników, jeśli brak - wysyła na główny
    chat = get_env_safe("T_CHAT_RESULTS") or get_env_safe("T_CHAT")

    if not token or not chat:
        print(f"⚠️ Telegram wynikowy pominięty: brak kluczy.")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=10)
    except: pass

def get_match_results(sport, event_id):
    """Pobiera wyniki meczu z API."""
    api_key = get_env_safe("ODDS_KEY")
    if not api_key:
        print("❌ Błąd: Brak ODDS_KEY w środowisku!")
        return None

    url = f"https://api.the-odds-api.com/v4/sports/{sport}/scores/"
    params = {
        "apiKey": api_key,
        "daysFrom": 3
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        if resp.status_code == 200:
            return resp.json()
        else:
            print(f"❌ API zwróciło kod {resp.status_code}")
    except Exception as e:
        print(f"❌ Błąd API przy sprawdzaniu wyniku: {e}")
    return None

def settle_matches():
    print(f"🚀 START ROZLICZANIA: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if not os.path.exists(COUPONS_FILE):
        print("ℹ️ Brak aktywnych kuponów do rozliczenia.")
        return

    try:
        with open(COUPONS_FILE, "r", encoding="utf-8") as f:
            active_coupons = json.load(f)
    except:
        print("❌ Błąd odczytu pliku kuponów.")
        return

    if not active_coupons:
        print("ℹ️ Lista kuponów jest pusta.")
        return

    history = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
        except: pass

    remaining_coupons = []
    new_settlements = 0

    # Grupowanie sportów, aby nie odpytywać API za każdym razem (oszczędność limitów)
    sports_to_check = list(set(c['sport'] for c in active_coupons))
    all_results = {}
    
    for sport in sports_to_check:
        results = get_match_results(sport, None)
        if results:
            for r in results:
                all_results[r['id']] = r

    for coupon in active_coupons:
        match_data = all_results.get(coupon['id'])

        if match_data and match_data.get('completed'):
            home_score, away_score = 0, 0
            for score in match_data.get('scores', []):
                if score['name'] == match_data['home_team']:
                    home_score = int(score['score'])
                else:
                    away_score = int(score['score'])

            # Sprawdzenie wygranej
            won = False
            # Remis w H2H traktujemy zazwyczaj jako przegraną (zależy od rynku)
            if coupon['outcome'] == match_data['home_team'] and home_score > away_score:
                won = True
            elif coupon['outcome'] == match_data['away_team'] and away_score > home_score:
                won = True

            stake = float(coupon.get('stake', 0))
            odds = float(coupon.get('odds', 0))

            if won:
                profit = (stake * odds) - stake
                status = "WIN"
                icon = "💰"
            else:
                profit = -stake
                status = "LOSS"
                icon = "❌"

            # Dodanie do historii
            res_entry = {
                "id": coupon['id'],
                "home": coupon['home'],
                "away": coupon['away'],
                "sport": coupon['sport'],
                "outcome": coupon['outcome'],
                "odds": odds,
                "stake": stake,
                "profit": round(profit, 2),
                "status": status,
                "score": f"{home_score}:{away_score}",
                "time": coupon['time']
            }
            history.append(res_entry)
            new_settlements += 1

            # Raport na Telegram
            msg = (f"{icon} <b>ROZLICZONO: {status}</b>\n"
                   f"━━━━━━━━━━━━━━━\n"
                   f"🏟 {coupon['home']} - {coupon['away']}\n"
                   f"🔢 Wynik: <b>{home_score}:{away_score}</b>\n"
                   f"✅ Typ: {coupon['outcome']}\n"
                   f"📈 Kurs: {odds}\n"
                   f"💵 Profit: <b>{profit:.2f} PLN</b>")
            send_telegram_result(msg)
            
            print(f"✅ Rozliczono: {coupon['home']} - {coupon['away']} | {status}")
        else:
            remaining_coupons.append(coupon)

    # Zapisywanie zmian
    if new_settlements > 0:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=4)
        with open(COUPONS_FILE, "w", encoding="utf-8") as f:
            json.dump(remaining_coupons, f, indent=4)
        print(f"🚀 Zakończono! Nowych meczów: {new_settlements}")
    else:
        print("ℹ️ Brak nowych meczów do rozliczenia.")

if __name__ == "__main__":
    settle_matches()
