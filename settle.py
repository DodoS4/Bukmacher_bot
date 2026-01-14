import json
import requests
import os
from datetime import datetime, timezone
from dateutil import parser

T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT_RESULTS")
API_KEYS = [
    os.getenv("ODDS_KEY"),
    os.getenv("ODDS_KEY_2"),
]

FILE = "coupons.json"
TAX = 0.12

def send(msg):
    requests.post(
        f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
        json={"chat_id": T_CHAT, "text": msg, "parse_mode": "HTML"},
        timeout=10,
    )

coupons = json.load(open(FILE, "r", encoding="utf-8"))
now = datetime.now(timezone.utc)

settled = 0

for c in coupons:
    if c["status"] != "pending":
        continue

    if parser.isoparse(c["date"]) > now:
        continue

    # SYMULACJA ROZLICZENIA (tu możesz podpiąć API wyników)
    won = c["odds"] < 2.0

    if won:
        profit = c["stake"] * c["odds"] * (1 - TAX) - c["stake"]
        c["status"] = "won"
        c["profit"] = round(profit, 2)
    else:
        c["status"] = "lost"
        c["profit"] = -c["stake"]

    settled += 1

json.dump(coupons, open(FILE, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
send(f"⚖️ Rozliczono kupony: <b>{settled}</b>")