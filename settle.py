import requests, json, os
from datetime import datetime, timezone, timedelta
from dateutil import parser

T_TOKEN = os.getenv("T_TOKEN")
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS")

API_KEYS = [os.getenv(f"ODDS_KEY{i}") for i in ["", "_2", "_3", "_4", "_5"]]
API_KEYS = [k for k in API_KEYS if k]

COUPONS_FILE = "coupons_notax.json"
TAX_PL = 1.0  # NO TAX

# ================= UTIL =================

def send_msg(txt):
    if not T_TOKEN or not T_CHAT_RESULTS:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
            json={"chat_id": T_CHAT_RESULTS, "text": txt, "parse_mode": "HTML"},
            timeout=10
        )
    except:
        pass

def load_coupons():
    if not os.path.exists(COUPONS_FILE):
        return []
    try:
        with open(COUPONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def save_coupons(data):
    with open(COUPONS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def fetch_scores(league_key):
    for key in API_KEYS:
        r = requests.get(
            f"https://api.the-odds-api.com/v4/sports/{league_key}/scores/",
            params={"apiKey": key, "daysFrom": 5},
            timeout=15
        )
        if r.status_code == 200:
            return r.json()
    return []

def norm(t):
    return t.lower().replace(".", "").replace("-", "").strip()

def team_match(a, b):
    a, b = norm(a), norm(b)
    return a in b or b in a

# ================= SETTLE =================

def run_settler():
    coupons = load_coupons()
    pending = [c for c in coupons if c.get("status") == "PENDING"]

    if not pending:
        print("[SETTLE] Brak PENDING")
        return

    print(f"[SETTLE] Pending: {len(pending)}")

    leagues = {c["league_key"] for c in pending}

    for league in leagues:
        scores = fetch_scores(league)
        print(f"[SETTLE] {league} | games: {len(scores)}")

        for c in coupons:
            if c.get("status") != "PENDING" or c["league_key"] != league:
                continue

            c_time = parser.isoparse(c["date"])

            for s in scores:
                if not s.get("completed"):
                    continue

                s_time = parser.isoparse(s["commence_time"])

                # ⏱️ time window ±6h
                if abs((s_time - c_time).total_seconds()) > 6 * 3600:
                    continue

                if not (
                    team_match(s["home_team"], c["home"]) and
                    team_match(s["away_team"], c["away"])
                ):
                    continue

                # ✅ MATCH FOUND
                try:
                    scores_map = {
                        sc["name"]: int(sc["score"])
                        for sc in s.get("scores", [])
                        if sc.get("score") is not None
                    }

                    h_score = next(
                        v for k, v in scores_map.items()
                        if team_match(k, c["home"])
                    )
                    a_score = next(
                        v for k, v in scores_map.items()
                        if team_match(k, c["away"])
                    )

                except:
                    continue

                winner = c["home"] if h_score > a_score else c["away"]
                c["status"] = "WON" if c["pick"] == winner else "LOST"

                if c["status"] == "WON":
                    profit = (c["stake"] * c["odds"] * TAX_PL) - c["stake"]
                    emoji = "✅"
                    res = f"Zysk: <b>+{round(profit,2)} zł</b>"
                else:
                    profit = -c["stake"]
                    emoji = "❌"
                    res = f"Strata: <b>{profit} zł</b>"

                c["profit"] = round(profit, 2)
                c["settled_at"] = datetime.now(timezone.utc).isoformat()

                msg = (
                    f"{emoji} <b>ROZLICZONO</b>\n"
                    f"{c['home']} vs {c['away']}\n"
                    f"Wynik: {h_score}:{a_score}\n"
                    f"Typ: {c['pick']}\n"
                    f"{res}"
                )

                send_msg(msg)
                print(f"[SETTLE] {c['home']} - {c['away']} | {c['status']}")
                break

    save_coupons(coupons)
    print("[SETTLE] Zapisano plik")

# ================= RUN =================

if __name__ == "__main__":
    run_settler()