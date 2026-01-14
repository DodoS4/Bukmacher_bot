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
            params={"apiKey": key, "daysFrom": 7},
            timeout=15
        )
        if r.status_code == 200:
            return r.json()
    return []

def norm(name):
    return (
        name.lower()
        .replace(".", "")
        .replace("-", "")
        .replace("fc ", "")
        .replace(" bk", "")
        .strip()
    )

def team_set(a, b):
    return {norm(a), norm(b)}

# ================= SETTLE =================

def run_settler():
    coupons = load_coupons()
    pending = [c for c in coupons if c.get("status") == "PENDING"]

    if not pending:
        print("[SETTLE] Brak PENDING")
        return

    print(f"[SETTLE] Pending coupons: {len(pending)}")

    leagues = {c["league_key"] for c in pending}

    for league in leagues:
        scores = fetch_scores(league)
        print(f"[SETTLE] {league} | API games: {len(scores)}")

        for c in coupons:
            if c.get("status") != "PENDING" or c["league_key"] != league:
                continue

            coupon_time = parser.isoparse(c["date"])
            coupon_teams = team_set(c["home"], c["away"])
            settled = False

            for s in scores:
                if not s.get("completed"):
                    continue

                if not s.get("scores"):
                    print(f"[SKIP] NO SCORES | {s.get('home_team')} - {s.get('away_team')}")
                    continue

                game_time = parser.isoparse(s["commence_time"])

                # ⏱️ ±24h window
                if abs((game_time - coupon_time).total_seconds()) > 24 * 3600:
                    print(f"[SKIP] TIME | {c['home']} - {c['away']}")
                    continue

                api_teams = team_set(s["home_team"], s["away_team"])

                if api_teams != coupon_teams:
                    print(f"[SKIP] TEAM | coupon={coupon_teams} api={api_teams}")
                    continue

                # ✅ MATCH FOUND
                try:
                    scores_map = {
                        norm(sc["name"]): int(sc["score"])
                        for sc in s["scores"]
                        if sc.get("score") is not None
                    }

                    h_score = scores_map[norm(c["home"])]
                    a_score = scores_map[norm(c["away"])]

                except Exception as e:
                    print(f"[SKIP] SCORE MAP ERROR | {e}")
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
                print(f"[SETTLE] OK | {c['home']} - {c['away']} | {c['status']}")
                settled = True
                break

            if not settled:
                print(f"[PENDING] {c['home']} - {c['away']}")

    save_coupons(coupons)
    print("[SETTLE] Zapisano coupons_notax.json")

# ================= RUN =================

if __name__ == "__main__":
    run_settler()