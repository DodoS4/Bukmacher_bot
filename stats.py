import json, os
from datetime import datetime
import requests

T_TOKEN = os.getenv("T_TOKEN")
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS")
FILE = "coupons_notax.json"

def tg(msg):
    if T_TOKEN and T_CHAT_RESULTS:
        try:
            requests.post(
                f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
                json={"chat_id": T_CHAT_RESULTS, "text": msg, "parse_mode": "HTML"}
            )
        except:
            pass

def run():
    if not os.path.exists(FILE):
        return

    with open(FILE, "r", encoding="utf-8") as f:
        try:
            coupons = json.load(f)
        except:
            return

    leagues = {}
    for c in coupons:
        lname = c["league"]
        if lname not in leagues:
            leagues[lname] = {"won":0,"lost":0,"profit":0,"bets":0}
        if c.get("status") in ["WON","LOST"]:
            leagues[lname]["bets"] += 1
            if c["status"]=="WON":
                leagues[lname]["won"] += 1
                leagues[lname]["profit"] += (c["stake"]*c["odds"]*1.0 - c["stake"])
            else:
                leagues[lname]["lost"] += 1
                leagues[lname]["profit"] -= c["stake"]

    msg = f"📊 <b>Raport dzienny lig</b> - {datetime.now().strftime('%d.%m.%Y')}\n\n"
    for lname,data in leagues.items():
        roi = (data["profit"]/ (data["bets"]*100) *100) if data["bets"]>0 else 0
        msg += f"{lname}: Bets {data['bets']} | Won {data['won']} | Lost {data['lost']} | ROI {roi:.2f}%\n"

    tg(msg)

if __name__=="__main__":
    run()