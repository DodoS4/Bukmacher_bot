import json
import os

def generate_stats():
    upcoming_count = 0
    groups = {}
    total_staked_in_game = 0.0
    
    if os.path.exists("coupons.json"):
        with open("coupons.json", "r") as f:
            try:
                coupons = json.load(f)
                upcoming_count = len(coupons)
                for c in coupons:
                    sport_raw = c.get('sport', 'Inne')
                    league = sport_raw.replace('soccer_', '').replace('icehockey_', '').replace('_', ' ').upper()
                    
                    if league not in groups:
                        groups[league] = {"matches": [], "total_potential_profit": 0.0}
                    
                    odds = float(c.get('odds', 0))
                    stake = float(c.get('stake', 0))
                    
                    # --- POTENCJALNY ZYSK NETTO (Z PODATKIEM 12%) ---
                    # (Stawka * 0.88 * Kurs) - Stawka
                    pot_profit = round((stake * 0.88 * odds) - stake, 2)
                    
                    groups[league]["matches"].append({
                        "teams": f"{c.get('home')} - {c.get('away')}",
                        "outcome": c.get('outcome'),
                        "odds": odds,
                        "stake": stake,
                        "profit": pot_profit
                    })
                    groups[league]["total_potential_profit"] += pot_profit
                    total_staked_in_game += stake
            except: pass

    sorted_groups = dict(sorted(groups.items(), key=lambda item: item[1]['total_potential_profit'], reverse=True))

    balance = 100.0
    if os.path.exists("bankroll.json"):
        with open("bankroll.json", "r") as f:
            balance = json.load(f).get("balance", 100.0)

    # Obliczanie obrotu z zabezpieczeniem przed duplikatami
    total_turnover = 0.0
    seen_ids = set()
    if os.path.exists("history.json"):
        with open("history.json", "r") as f:
            try:
                history = json.load(f)
                for h in history:
                    if h.get('id') not in seen_ids:
                        total_turnover += float(h.get('stake', 0))
                        seen_ids.add(h.get('id'))
            except: pass

    stats_data = {
        "balance": balance,
        "upcoming_count": upcoming_count,
        "total_profit": round(balance - 100.0, 2),
        "roi": f"{round(((balance - 100.0) / 100.0) * 100, 2) if balance != 100 else 0}%",
        "turnover": round(total_turnover, 2),
        "in_game_amount": round(total_staked_in_game, 2),
        "groups": sorted_groups,
        "last_update": os.popen('date "+%H:%M:%S"').read().strip()
    }

    with open("stats.json", "w") as f:
        json.dump(stats_data, f, indent=4)
    print("✅ Statystyki zaktualizowane (uwzględniono podatek 12%).")

if __name__ == "__main__":
    generate_stats()
