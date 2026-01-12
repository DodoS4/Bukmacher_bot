import json, os
from datetime import datetime, timezone
import requests

T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT_RESULTS")
FILE = "coupons_notax.json"

def load():
    with open(FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save(data):
    with open(FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def tg(msg):
    if T_TOKEN and T_CHAT:
        requests.post(
            f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
            json={"chat_id": T_CHAT, "text": msg, "parse_mode": "HTML"}
        )

def run():
    data = load()
    for c in data:
        if c["status"] != "PENDING" or c["notified"]:
            continue

        if c["result"] is None:
            continue

        if c["result"] == "WIN":
            c["profit"] = round(c["stake"] * (c["odds"] - 1), 2)
            res = "✅ WYGRANA"
        else:
            c["profit"] = -c["stake"]
            res = "❌ PRZEGRANA"

        c["status"] = "SETTLED"
        c["settled_at"] = datetime.now(timezone.utc).isoformat()
        c["notified"] = True

        tg(
            f"{res}\n"
            f"{c['home']} vs {c['away']}\n"
            f"Profit: <b>{c['profit']} zł</b>"
        )

    save(data)

if __name__ == "__main__":
    run()