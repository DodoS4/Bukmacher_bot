import requests, json, os
from datetime import datetime

T_TOKEN = os.getenv("T_TOKEN")
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS")
API_KEY = os.getenv("ODDS_KEY")

USE_TAX = False
TAX_PL = 1.0

COUPONS_FILE = "coupons_notax.json"

def send_msg(txt):
    if not T_TOKEN or not T_CHAT_RESULTS:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
            json={"chat_id": T_CHAT_RESULTS, "text": txt, "parse_mode": "HTML"}
        )
    except:
        pass

def run_settler():
    if not os.path.exists(COUPONS_FILE):
        return

    with open(COUPONS_FILE, "r", encoding="utf-8") as f:
        coupons = json.load(f)

    pending = [c for c in coupons if c["status"] == "PENDING"]
    if not pending:
        return

    leagues = {c["league_key"] for c in pending}

    for l in leagues:
        r = requests.get(
            f"https://api.the-odds-api.com/v4/sports/{l}/scores/",
            params={"apiKey": API_KEY, "daysFrom": 3}
        )
        if r.status_code != 200:
            continue

        scores = r.json()

        for c in coupons:
            if c["status"] != "PENDING" or c["league_key"] != l:
                continue

            match = next(
                (s for s in scores
                 if s["home_team"] == c["home"] and s["away_team"] == c["away"]
                 and s.get("completed")),
                None
            )
            if not match:
                continue

            score_map = {x["name"]: int(x["score"]) for x in match["scores"]}
            h, a = score_map[c["home"]], score_map[c["away"]]
            winner = c["home"] if h > a else c["away"]

            if c["pick"] == winner:
                c["status"] = "WON"
                profit = c["stake"] * c["odds"] * TAX_PL - c["stake"]
                msg = f"✅ {c['home']} - {c['away']} {h}:{a}\nZysk: <b>+{profit:.2f} zł</b>"
            else:
                c["status"] = "LOST"
                msg = f"❌ {c['home']} - {c['away']} {h}:{a}\nStrata: <b>-{c['stake']} zł</b>"

            send_msg(msg)

    with open(COUPONS_FILE, "w", encoding="utf-8") as f:
        json.dump(coupons, f, indent=2)

if __name__ == "__main__":
    run_settler()