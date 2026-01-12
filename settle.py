import requests, json, os

T_TOKEN = os.getenv("T_TOKEN")
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS")
FILE = "coupons_notax.json"
TAX_PL = 1.0

def send_msg(txt):
    if not T_TOKEN or not T_CHAT_RESULTS: return
    try:
        requests.post(
            f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
            json={"chat_id":T_CHAT_RESULTS,"text":txt,"parse_mode":"HTML"}
        )
    except: pass

def load():
    if os.path.exists(FILE):
        with open(FILE,"r",encoding="utf-8") as f:
            try: return json.load(f)
            except: return []
    return []

def save(data):
    with open(FILE,"w",encoding="utf-8") as f: json.dump(data,f,indent=2)

def run():
    coupons = load()
    if not coupons: return

    for c in coupons:
        if c['status'] != "PENDING": continue
        # Testowe rozliczenie: losowo ustalamy wynik dla demo
        from random import choice
        winner = choice([c['home'], c['away']])
        c['status'] = "WON" if c['pick']==winner else "LOST"
        if c['status']=="WON":
            profit = round(c['stake']*c['odds']*TAX_PL - c['stake'],2)
            c['profit'] = profit
            txt = f"✅ ROZLICZONO: {c['home']} - {c['away']}\nTyp: {c['pick']} | Zysk: +{profit} zł"
        else:
            c['profit'] = -c['stake']
            txt = f"❌ ROZLICZONO: {c['home']} - {c['away']}\nTyp: {c['pick']} | Strata: -{c['stake']} zł"
        send_msg(txt)

    save(coupons)

if __name__=="__main__":
    run()