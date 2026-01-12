import requests, json, os
from datetime import datetime, timezone

T_TOKEN = os.getenv("T_TOKEN")
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS")
API_KEY = os.getenv("ODDS_KEY")
FILE = "coupons_notax.json"
TAX = 1.0  # NO TAX

# ===== HELPERS =====
def tg(msg):
    if T_TOKEN and T_CHAT_RESULTS:
        try:
            requests.post(
                f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
                json={"chat_id": T_CHAT_RESULTS, "text": msg, "parse_mode": "HTML"}
            )
        except:
            pass

def load():
    if not os.path.exists(FILE):
        with open(FILE, "w", encoding="utf-8") as f:
            json.dump([], f)
        return []
    with open(FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except:
            return []

def save(data):
    with open(FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

# ===== MAIN =====
def run():
    coupons = load()
    pending = [c for c in coupons if c.get("status") == "PENDING"]
    if not pending:
        return

    leagues = {c["league"] for c in pending}

    for lkey in leagues:
        url = f"https://api.the-odds-api.com/v4/sports/{lkey}/scores/"
        try:
            r = requests.get(url, params={"apiKey": API_KEY, "daysFrom": 3})
            if r.status_code != 200:
                continue
            scores = r.json()
        except:
            continue

        for c in coupons:
            if c.get("status") != "PENDING" or c["league"] != lkey:
                continue

            match = next(
                (s for s in scores if s["home_team"] == c["home"] or s["away_team"] == c["home"]),
                None
            )
            if not match or not match.get("completed"):
                continue

            try:
                score_map = {s["name"]: int(s["score"]) for s in match["scores"]}
                h_score = score_map.get(c["home"])
                a_score = score_map.get(c["away"])
                if h_score is None or a_score is None:
                    continue

                winner = c["home"] if h_score > a_score else c["away"]
                c["status"] = "WON" if c["pick"] == winner else "LOST"

                if c["status"] == "WON":
                    profit = (c["stake"] * c["odds"] * TAX) - c["stake"]
                    emoji = "✅"
                    result_text = f"Zysk: <b>+{round(profit, 2)} zł</b>"
                else:
                    emoji = "❌"
                    result_text = f"Strata: <b>-{c['stake']} zł</b>"

                txt = (
                    f"{emoji} <b>ROZLICZONO: {c['home']} - {c['away']}</b>\n"
                    f"Wynik: {h_score}:{a_score}\n"
                    f"Typ: {c['pick']} | {result_text}"
                )
                tg(txt)

            except:
                continue

    save(coupons)

if __name__ == "__main__":
    run()