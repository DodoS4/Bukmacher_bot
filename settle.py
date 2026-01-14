import requests, json, os, time
from datetime import datetime, timezone
from dateutil import parser

FILE = "coupons.json"
TAX = 0.12
MAX_ATTEMPTS = 7

T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT_RESULTS")

API_KEYS = [
    os.getenv("ODDS_KEY"),
    os.getenv("ODDS_KEY_2"),
    os.getenv("ODDS_KEY_3"),
    os.getenv("ODDS_KEY_4"),
    os.getenv("ODDS_KEY_5"),
]

def send(msg):
    if not T_TOKEN or not T_CHAT:
        return
    requests.post(
        f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
        json={"chat_id": T_CHAT, "text": msg},
        timeout=10
    )

def norm(name):
    return (
        name.lower()
        .replace(".", "")
        .replace("-", " ")
        .replace("los angeles", "la")
        .replace("new york", "ny")
        .strip()
    )

def fetch_scores(league, days):
    for key in API_KEYS:
        if not key:
            continue
        r = requests.get(
            f"https://api.the-odds-api.com/v4/sports/{league}/scores",
            params={"apiKey": key, "daysFrom": days},
            timeout=15,
        )
        if r.status_code == 200:
            return r.json()
    return []

coupons = json.load(open(FILE, encoding="utf-8"))
now = datetime.now(timezone.utc)

for c in coupons:
    if c.get("status") != "pending":
        continue

    c.setdefault("settle_attempts", 0)
    c.setdefault("last_checked", None)

    if c["settle_attempts"] >= MAX_ATTEMPTS:
        c["status"] = "ERROR_NO_DATA"
        continue

    days = 3 if c["settle_attempts"] < 3 else 7
    scores = fetch_scores(c["league"], days)

    found = False

    for g in scores:
        if not g.get("completed"):
            continue

        if (
            norm(g["home_team"]) == norm(c["home"])
            and norm(g["away_team"]) == norm(c["away"])
        ) or (
            norm(g["home_team"]) == norm(c["away"])
            and norm(g["away_team"]) == norm(c["home"])
        ):
            try:
                s = {x["name"]: int(x["score"]) for x in g["scores"]}
                h = s.get(g["home_team"])
                a = s.get(g["away_team"])
                if h is None or a is None:
                    continue

                winner = g["home_team"] if h > a else g["away_team"]

                if norm(winner) == norm(c["pick"]):
                    profit = c["stake"] * c["odds"] * (1 - TAX) - c["stake"]
                    c["status"] = "won"
                    c["profit"] = round(profit, 2)
                    emoji = "✅"
                else:
                    c["status"] = "lost"
                    c["profit"] = -c["stake"]
                    emoji = "❌"

                send(
                    f"{emoji} ROZLICZONO\n"
                    f"{c['home']} vs {c['away']}\n"
                    f"Wynik: {h}:{a}\n"
                    f"Typ: {c['pick']}\n"
                    f"💰 {c['profit']} zł"
                )

                found = True
                break
            except:
                continue

    c["settle_attempts"] += 1
    c["last_checked"] = now.isoformat()

    if not found:
        time.sleep(0.3)

json.dump(coupons, open(FILE, "w", encoding="utf-8"), indent=2, ensure_ascii=False)