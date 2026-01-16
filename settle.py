import json
from datetime import datetime
import requests

COUPON_FILE = "coupons.json"
RESULTS_FILE = "results.json"
BANKROLL_FILE = "bankroll.json"
TELEGRAM_TOKEN = "<T_TOKEN>"
TELEGRAM_CHAT = "<T_CHAT>"

STAKE_PERCENT = 0.02  # 2% BR na typ

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": TELEGRAM_CHAT, "text": message, "parse_mode": "Markdown"})

def load_coupons():
    with open(COUPON_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def load_bankroll():
    try:
        with open(BANKROLL_FILE, "r") as f:
            return json.load(f)
    except:
        return {"bankroll": 1000}  # startowy BR

def save_bankroll(br):
    with open(BANKROLL_FILE, "w") as f:
        json.dump(br, f, ensure_ascii=False, indent=4)

def settle_coupons(coupons):
    bankroll_data = load_bankroll()
    bankroll = bankroll_data["bankroll"]
    results = []
    now = datetime.utcnow()

    for c in coupons:
        match_time = datetime.fromisoformat(c["time"])
        if match_time > now:
            continue

        stake = bankroll * STAKE_PERCENT
        # PROSTE: losowy wynik (do zamiany na live API wyników)
        from random import choice
        outcome = choice([c["pick"], "other"])
        profit = stake * (c["odds"] - 1) if outcome == c["pick"] else -stake
        bankroll += profit

        results.append({
            "match": f"{c['home']} vs {c['away']}",
            "pick": c["pick"],
            "result": outcome,
            "profit": profit
        })
        send_telegram(f"⚡ {c['home']} vs {c['away']} | Pick: {c['pick']} | Result: {outcome} | Profit: {profit:.2f}")

    save_bankroll({"bankroll": bankroll})
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=4)

    print(f"[INFO] Rozliczono {len(results)} kuponów | BR: {bankroll:.2f}")

if __name__ == "__main__":
    coupons = load_coupons()
    settle_coupons(coupons)