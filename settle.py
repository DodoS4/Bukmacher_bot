import os
import json
import requests
from datetime import datetime

# --- KONFIGURACJA ---
COUPONS_FILE = "coupons.json"
HISTORY_FILE = "history.json"
BANKROLL_FILE = "bankroll.json"
# Klucz API do pobierania wyników (używamy pierwszego z listy)
API_KEY = os.getenv("ODDS_KEY_1") or os.getenv("ODDS_KEY")

def update_bankroll(amount):
    """Aktualizuje saldo w bankroll.json."""
    balance = 100.0
    if os.path.exists(BANKROLL_FILE):
        with open(BANKROLL_FILE, "r") as f:
            data = json.load(f)
            balance = data.get("balance", 100.0)
    
    new_balance = round(balance + amount, 2)
    with open(BANKROLL_FILE, "w") as f:
        json.dump({"balance": new_balance}, f)
    return new_balance

def send_telegram_result(message):
    token = os.getenv("T_TOKEN")
    chat_id = os.getenv("T_CHAT_RESULTS") or os.getenv("T_CHAT")
    if token and chat_id:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
        requests.post(url, json=payload)

def settle_bets():
    if not os.path.exists(COUPONS_FILE):
        print("ℹ️ Brak aktywnych kuponów do rozliczenia.")
        return

    with open(COUPONS_FILE, "r") as f:
        coupons = json.load(f)

    if not coupons:
        print("ℹ️ Lista kuponów jest pusta.")
        return

    remaining_coupons = []
    history = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            try: history = json.load(f)
            except: history = []

    print(f"\n{'='*40}")
    print(f"🏟 ROZLICZANIE WYNIKÓW (Debug Mode)")
    print(f"{'='*40}")

    for c in coupons:
        sport = c['sport']
        # Pobieramy wyniki dla konkretnej ligi
        url = f"https://api.the-odds-api.com/v4/sports/{sport}/scores/"
        params = {"apiKey": API_KEY, "daysFrom": 3}
        
        try:
            resp = requests.get(url, params=params)
            if resp.status_code != 200:
                remaining_coupons.append(c)
                continue
            
            scores = resp.json()
            # Szukamy meczu po ID
            match_result = next((m for m in scores if m['id'] == c['id']), None)

            if match_result and match_result.get('completed'):
                home_score = 0
                away_score = 0
                # Pobieramy punkty/bramki
                for s in match_result.get('scores', []):
                    if s['name'] == match_result['home_team']: home_score = int(s['score'])
                    if s['name'] == match_result['away_team']: away_score = int(s['score'])

                # LOGIKA ROZSTRZYGNIĘCIA
                won = False
                final_result = f"{home_score}:{away_score}"
                
                # Sprawdzamy co postawił bot
                if c['outcome'] == match_result['home_team'] and home_score > away_score: won = True
                elif c['outcome'] == match_result['away_team'] and away_score > home_score: won = True
                elif c['outcome'] == "Draw" and home_score == away_score: won = True

                profit = round(c['stake'] * c['odds'] - c['stake'], 2) if won else -c['stake']
                
                # Aktualizacja bankrolla (Kula Śnieżna)
                new_bal = update_bankroll(profit if won else -c['stake'])
                
                status_icon = "✅ WYGRANA" if won else "❌ PRZEGRANA"
                print(f"{status_icon}: {c['home']} - {c['away']} ({final_result}) | Zysk: {profit} PLN")

                # Dodajemy do historii
                c['status'] = "WON" if won else "LOST"
                c['score'] = final_result
                c['profit'] = profit
                c['settled_at'] = datetime.now().isoformat()
                history.append(c)

                # Powiadomienie Telegram
                msg = (
                    f"{status_icon}\n"
                    f"🏟 {c['home']} - {c['away']}\n"
                    f"🏆 Wynik: `{final_result}`\n"
                    f"💰 Profit: `{profit:+.2f} PLN`\n"
                    f"🏦 Bankroll: `{new_bal:.2f} PLN`"
                )
                send_telegram_result(msg)
            else:
                # Mecz jeszcze trwa lub nie ma wyniku
                remaining_coupons.append(c)
                print(f"⏳ W TRAKCIE: {c['home']} - {c['away']}")

        except Exception as e:
            print(f"⚠️ Błąd rozliczania {c['id']}: {e}")
            remaining_coupons.append(c)

    # Zapisz zaktualizowane pliki
    with open(COUPONS_FILE, "w") as f:
        json.dump(remaining_coupons, f, indent=4)
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=4)

    print(f"\n✅ Sesja zakończona. Pozostało w grze: {len(remaining_coupons)}")
    print(f"{'='*40}\n")

if __name__ == "__main__":
    settle_bets()
