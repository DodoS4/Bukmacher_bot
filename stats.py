import json, os
from collections import defaultdict

COUPONS_FILE = "coupons_notax.json"

def load_coupons():
    if not os.path.exists(COUPONS_FILE): return []
    try:
        with open(COUPONS_FILE,"r",encoding="utf-8") as f:
            return json.load(f)
    except: return []

def run_stats():
    coupons = load_coupons()
    total = len(coupons)
    won = sum(1 for c in coupons if c.get("status")=="WON")
    lost = sum(1 for c in coupons if c.get("status")=="LOST")
    profit = sum((c["stake"]*c["odds"]-c["stake"] if c.get("status")=="WON" else -c["stake"]) for c in coupons)

    print("📊 Statystyki wszystkich lig")
    print(f"Łącznie zakładów: {total}")
    print(f"✅ Wygrane: {won}")
    print(f"❌ Przegrane: {lost}")
    print(f"💰 Zysk/Strata: {round(profit,2)} zł\n")

    by_league = defaultdict(list)
    for c in coupons: by_league[c["league"]].append(c)

    print("Podział na ligi:")
    for l, lst in by_league.items():
        l_total = len(lst)
        l_won = sum(1 for x in lst if x.get("status")=="WON")
        l_lost = sum(1 for x in lst if x.get("status")=="LOST")
        l_profit = sum((x["stake"]*x["odds"]-x["stake"] if x.get("status")=="WON" else -x["stake"]) for x in lst)
        print(f"{l}: Bets {l_total} | ✅ {l_won} | ❌ {l_lost} | 💰 {round(l_profit,2)} zł")

if __name__=="__main__":
    run_stats()