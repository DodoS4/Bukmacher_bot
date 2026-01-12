import json, os
from collections import defaultdict
import requests

T_TOKEN = os.getenv("T_TOKEN")
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS")
FILE = "coupons_notax.json"

def tg(msg):
    if T_TOKEN and T_CHAT_RESULTS:
        try:
            requests.post(
                f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
                json={"chat_id":T_CHAT_RESULTS,"text":msg,"parse_mode":"HTML"}
            )
        except: pass

def load():
    if os.path.exists(FILE):
        with open(FILE,"r",encoding="utf-8") as f:
            try: return json.load(f)
            except: return []
    return []

def run():
    coupons = load()
    if not coupons:
        tg("📊 Statystyki: brak zakładów w pliku.")
        return

    stats = defaultdict(lambda: {"WON":0,"LOST":0,"profit":0.0,"bets":0})
    total_bets = total_won = total_lost = total_profit = 0

    for c in coupons:
        league = c['league']
        stats[league]['bets'] += 1
        total_bets += 1
        if c['status']=="WON":
            stats[league]['WON'] +=1
            stats[league]['profit'] += c.get('profit',0)
            total_won +=1
            total_profit += c.get('profit',0)
        elif c['status']=="LOST":
            stats[league]['LOST'] +=1
            stats[league]['profit'] += c.get('profit',0)
            total_lost +=1
            total_profit += c.get('profit',0)

    msg = f"📊 <b>Statystyki wszystkich lig</b>\n\n"
    msg += f"Łącznie zakładów: {total_bets}\n✅ Wygrane: {total_won}\n❌ Przegrane: {total_lost}\n💰 Zysk/Strata: {round(total_profit,2)} zł\n\n"
    msg += "<b>Podział na ligi:</b>\n"
    for league, data in stats.items():
        msg += f"{league}: Bets {data['bets']} | ✅ {data['WON']} | ❌ {data['LOST']} | 💰 {round(data['profit'],2)} zł\n"

    tg(msg)

if __name__=="__main__":
    run()