import json
import os

# --- KONFIGURACJA PLIKÓW ---
COUPONS_FILE = "coupons.json"
HISTORY_FILE = "history.json"
BANKROLL_FILE = "bankroll.json"
STATS_FILE = "stats.json"

def generate_stats():
    upcoming_count = 0
    groups = {}
    total_staked_in_game = 0.0
    
    # 1. PRZETWARZANIE AKTYWNYCH KUPONÓW
    if os.path.exists(COUPONS_FILE):
        with open(COUPONS_FILE, "r") as f:
            try:
                coupons = json.load(f)
                upcoming_count = len(coupons)
                
                for c in coupons:
                    # Czyścimy nazwę ligi dla lepszego wyglądu
                    sport_raw = c.get('sport', 'Inne')
                    league_name = sport_raw.replace('soccer_', '').replace('icehockey_', '').replace('basketball_', '').replace('_', ' ').upper()
                    
                    if league_name not in groups:
                        groups[league_name] = {"matches": [], "total_potential_profit": 0.0}
                    
                    # Obliczamy potencjalny zysk netto (stawka * kurs - stawka)
                    odds = float(c.get('odds', 0))
                    stake = float(c.get('stake', 0))
                    pot_profit = round((stake * odds) - stake, 2)
                    
                    groups[league_name]["matches"].append({
                        "teams": f"{c.get('home')} - {c.get('away')}",
                        "outcome": c.get('outcome'),
                        "odds": odds,
                        "stake": stake,
                        "profit": pot_profit
                    })
                    
                    groups[league_name]["total_potential_profit"] += pot_profit
                    total_staked_in_game += stake
                    
            except Exception as e:
                print(f"⚠️ Błąd podczas czytania coupons.json: {e}")

    # 2. SORTOWANIE GRUP WEDŁUG NAJWYŻSZEGO ZYSKU
    sorted_groups = dict(sorted(
        groups.items(), 
        key=lambda item: item[1]['total_potential_profit'], 
        reverse=True
    ))

    # 3. POBIERANIE BANKROLLA
    balance = 100.0
    if os.path.exists(BANKROLL_FILE):
        with open(BANKROLL_FILE, "r") as f:
            try:
                data = json.load(f)
                balance = float(data.get("balance", 100.0))
            except:
                balance = 100.0

    # 4. STATYSTYKI HISTORYCZNE (Obrót, ROI)
    total_turnover = 0.0
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            try:
                history = json.load(f)
                total_turnover = sum(float(c.get('stake', 0)) for c in history)
            except:
                pass

    total_profit = round(balance - 100.0, 2)
    roi_val = round(((balance - 100.0) / 100.0) * 100, 2)

    # 5. BUDOWANIE FINALNEGO JSONA DLA DASHBOARDU
    stats_data = {
        "balance": balance,
        "upcoming_count": upcoming_count,
        "total_profit": total_profit,
        "roi": f"{roi_val}%",
        "turnover": total_turnover,
        "in_game_amount": round(total_staked_in_game, 2),
        "groups": sorted_groups,
        "last_update": os.popen('date "+%d.%m.%Y %H:%M:%S"').read().strip()
    }

    # Zapis do pliku
    with open(STATS_FILE, "w") as f:
        json.dump(stats_data, f, indent=4)
    
    print(f"✅ STATS SUCCESS: Przetworzono {upcoming_count} meczów w {len(sorted_groups)} ligach.")
    print(f"💰 Potencjał zysku w grze: {round(sum(g['total_potential_profit'] for g in sorted_groups.values()), 2)} PLN")

if __name__ == "__main__":
    generate_stats()
