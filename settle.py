import json
from datetime import datetime, timedelta

COUPON_FILE = "coupons.json"
RESULTS_FILE = "results.json"
TELEGRAM_TOKEN = "<T_TOKEN>"
TELEGRAM_CHAT = "<T_CHAT>"

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    import requests
    requests.post(url, data={"chat_id": TELEGRAM_CHAT, "text": message, "parse_mode": "Markdown"})

def load_coupons():
    with open(COUPON_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def settle_coupons(coupons):
    results = []
    now = datetime.utcnow()
    for c in coupons:
        match_time = datetime.fromisoformat(c["time"])
        if match_time > now:
            continue
        # PROSTE: losowy wynik symulowany (do podmiany na live API)
        from random import choice
        outcome = choice([c["pick"], "other"])
        profit = c["odds"] if outcome == c["pick"] else -1
        results.append({"match": f"{c['home']} vs {c['away']}", "pick": c["pick"], "result": outcome, "profit": profit})
    return results

def main():
    coupons = load_coupons()
    results = settle_coupons(coupons)
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=4)
    for r in results:
        send_telegram(f"⚡ {r['match']} | Pick: {r['pick']} | Result: {r['result']} | Profit: {r['profit']}")
    print(f"[INFO] Rozliczono {len(results)} kuponów")

if __name__ == "__main__":
    main()