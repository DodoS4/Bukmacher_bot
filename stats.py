import json, os
from collections import defaultdict

FILE = "coupons_notax.json"

def load():
    if os.path.exists(FILE):
        with open(FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except:
                return []
    return []

def run():
    coupons = load()
    stats = defaultdict(lambda: {"WON":0,"LOST":0,"profit":0.0,"bets":0})

    for c in coupons:
        league = c['league']
        stats[league]['bets'] += 1
        if c['status']=="WON":
            stats[league]['WON'] += 1
            stats[league]['profit'] += c.get('profit',0)
        elif c['status']=="LOST":
            stats[league]['LOST'] += 1
            stats[league]['profit'] += c.get('profit',0)

    print("\n📊 STATYSTYKI LIG / SPORTÓW")
    for league, data in stats.items():
        print(f"{league}: Bets {data['bets']} | WON {data['WON']} | LOST {data['LOST']} | Profit {round(data['profit'],2)} zł")
    print("\n")

if __name__=="__main__":
    run()