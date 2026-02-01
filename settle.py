import os
import json
import requests
from datetime import datetime, timezone

# --- KONFIGURACJA PLIKÓW ---
COUPONS_FILE = "coupons.json"
HISTORY_FILE = "history.json"

def get_all_api_keys():
    """Pobiera listę kluczy API z sekretów GitHub."""
    keys = []
    for i in range(1, 11):
        key_name = "ODDS_KEY" if i == 1 else f"ODDS_KEY_{i}"
        val = os.getenv(key_name)
        if val: keys.append(val)
    return keys

def get_bulk_results(sport, keys):
    """Pobiera wyniki dla całej ligi za jednym razem."""
    for key in keys:
        url = f"https://api.the-odds-api.com/v4/sports/{sport}/scores/"
        params = {"apiKey": key, "daysFrom": 3}
        try:
            resp = requests.get(url, params=params, timeout=15)
            if resp.status_code == 200:
                return resp.json()
        except:
            continue
    return None

def settle_matches():
    # Sprawdzenie czy są kupony
    if not os.path.exists(COUPONS_FILE):
        return
    with open(COUPONS_FILE, "r", encoding="utf-8") as f:
        active_coupons = json.load(f)
    if not active_coupons:
        return

    api_keys = get_all_api_keys()
    history = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
        except:
            pass

    # Grupowanie lig i pobieranie wyników
    sports_to_check = list(set(c['sport'] for c in active_coupons))
    results_map = {}
    for sport in sports_to_check:
        data = get_bulk_results(sport, api_keys)
        if data:
            for match in data:
                results_map[match['id']] = match

    remaining_coupons = []
    new_settlements = 0
    
    # Nagłówek logów
    log_output = []

    for coupon in active_coupons:
        match_data = results_map.get(coupon['id'])

        # Rozliczamy tylko jeśli mecz jest oznaczony jako ZAKOŃCZONY (completed)
        if match_data and match_data.get('completed'):
            h_score, a_score = 0, 0
            for score in match_data.get('scores', []):
                if score['name'] == match_data['home_team']:
                    h_score = int(score['score'])
                else:
                    away_score = int(score['score'])

            # Logika WIN / LOSS
            won = False
            pick = coupon['outcome']
            if pick == match_data['home_team'] and h_score > a_score:
                won = True
            elif pick == match_data['away_team'] and away_score > h_score:
                won = True

            stake = float(coupon['stake'])
            odds = float(coupon['odds'])
            profit = round((stake * odds) - stake if won else -stake, 2)
            
            status_icon = "💰 WIN " if won else "❌ LOSS"
            
            # Dodajemy linię do raportu
            log_output.append(f"{status_icon} | {coupon['home']} - {coupon['away']} | {h_score}:{a_score} | {profit} PLN")

            # Dodanie do historii
            history.append({
                "id": coupon['id'],
                "home": coupon['home'],
                "away": coupon['away'],
                "sport": coupon['sport'],
                "outcome": pick,
                "odds": odds,
                "stake": stake,
                "profit": profit,
                "status": "WIN" if won else "LOSS",
                "score": f"{h_score}:{a_score}",
                "time": coupon['time']
            })
            new_settlements += 1
        else:
            # Mecz w toku lub brak wyniku - zostaje na liście
            remaining_coupons.append(coupon)

    # WYŚWIETLANIE LOGÓW (Tylko rozliczone)
    if new_settlements > 0:
        print(f"\n--- ROZLICZONE MECZE ({datetime.now().strftime('%H:%M')}) ---")
        for line in log_output:
            print(line)
        print(f"------------------------------------------")
        print(f"✅ Łącznie rozliczono: {new_settlements}")
        
        # Zapis do plików
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=4)
        with open(COUPONS_FILE, "w", encoding="utf-8") as f:
            json.dump(remaining_coupons, f, indent=4)
    else:
        # Jeśli nic się nie rozliczyło, log jest bardzo krótki
        print(f"ℹ️ {datetime.now().strftime('%H:%M')} - Brak nowych rozliczeń (mecze trwają).")

if __name__ == "__main__":
    settle_matches()
