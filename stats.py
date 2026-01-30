import json
import os

def generate_stats():
    # 1. Liczymy kupony w grze
    upcoming_count = 0
    total_staked_in_game = 0.0
    
    if os.path.exists("coupons.json"):
        with open("coupons.json", "r") as f:
            try:
                coupons = json.load(f)
                upcoming_count = len(coupons)
                # Opcjonalnie: liczymy ile kasy jest aktualnie zamrożone w typach
                total_staked_in_game = sum(float(c.get('stake', 0)) for c in coupons)
            except Exception as e:
                print(f"Błąd czytania coupons.json: {e}")
                upcoming_count = 0

    # 2. Pobieramy aktualny bankroll
    balance = 100.0
    if os.path.exists("bankroll.json"):
        with open("bankroll.json", "r") as f:
            try:
                data = json.load(f)
                balance = float(data.get("balance", 100.0))
            except:
                balance = 100.0

    # 3. Pobieramy historię dla statystyk zysku i ROI
    total_profit = round(balance - 100.0, 2)
    roi = 0.0
    yield_val = 0.0
    total_turnover = 0.0
    
    if os.path.exists("history.json"):
        with open("history.json", "r") as f:
            try:
                history = json.load(f)
                total_turnover = sum(float(c.get('stake', 0)) for c in history)
                if total_turnover > 0:
                    yield_val = round((total_profit / total_turnover) * 100, 2)
                roi = round(((balance - 100.0) / 100.0) * 100, 2)
            except:
                pass

    # 4. Tworzymy finalny obiekt stats.json dla strony WWW
    # WAŻNE: Nazwy kluczy muszą być identyczne z tymi, których szuka Twój plik HTML!
    stats_data = {
        "balance": balance,
        "upcoming_count": upcoming_count,
        "total_profit": total_profit,
        "roi": f"{roi}%",
        "yield": f"{yield_val}%",
        "turnover": total_turnover,
        "in_game_amount": total_staked_in_game,
        "last_update": os.popen('date').read().strip() # Dodajemy czas aktualizacji dla debugu
    }

    with open("stats.json", "w") as f:
        json.dump(stats_data, f, indent=4)
    
    print(f"✅ STATS UPDATE SUCCESS!")
    print(f"📊 W grze: {upcoming_count}")
    print(f"🏦 Portfel: {balance} PLN")

if __name__ == "__main__":
    generate_stats()
