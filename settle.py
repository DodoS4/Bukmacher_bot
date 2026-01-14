import requests
import json
import os
from datetime import datetime

# ================== CONFIG ==================

T_TOKEN = os.getenv("T_TOKEN")
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS")

API_KEYS = [os.getenv(f"ODDS_KEY{i}") for i in ["", "_2", "_3", "_4", "_5"]]
API_KEYS = [k for k in API_KEYS if k]

COUPONS_FILE = "coupons_notax.json"
TAX_PL = 1.0  # NO TAX

AUTO_SETTLE_LEAGUES = {
    "basketball_nba",
    "soccer_epl",
    "soccer_laliga",
    "soccer_bundesliga",
    "soccer_serie_a",
    "soccer_ligue_1",
    "soccer_uefa_champs_league",
    "soccer_uefa_europa_league",
    "soccer_uefa_conference_league",
}

# ================== HELPERS ==================

def send_msg(text):
    if not T_TOKEN or not T_CHAT_RESULTS:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
            json={
                "chat_id": T_CHAT_RESULTS,
                "text": text,
                "parse_mode": "HTML"
            },
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
        json.dump(data, f, indent=2, ensure_ascii=False)


def fetch_scores(league_key):
    for key in API_KEYS:
        try:
            r = requests.get(
                f"https://api.the-odds-api.com/v4/sports/{league_key}/scores/",
                params={"apiKey": key, "daysFrom": 3},
                timeout=10
            )
            if r.status_code == 200:
                return r.json()
        except:
            continue
    return []

# ================== MAIN ==================

def run_settler():
    coupons = load_coupons()
    pending = [c for c in coupons if c.get("status") == "PENDING"]

    print(f"[SETTLE] Pending coupons: {len(pending)}")

    if not pending:
        return

    leagues = {c["league_key"] for c in pending}

    for league_key in leagues:

        if league_key not in AUTO_SETTLE_LEAGUES:
            print(f"[SKIP] {league_key} – brak auto settle")
            continue

        scores = fetch_scores(league_key)
        print(f"[SETTLE] {league_key} | API games: {len(scores)}")

        if not scores:
            continue

        for c in coupons:
            if c.get("status") != "PENDING":
                continue
            if c["league_key"] != league_key:
                continue

            game = next(
                (
                    g for g in scores
                    if g.get("home_team") == c["home"]
                    and g.get("away_team") == c["away"]
                ),
                None
            )

            if not game or not game.get("completed"):
                print(f"[PENDING] {c['home']} - {c['away']}")
                continue

            try:
                score_map = {s["name"]: int(s["score"]) for s in game["scores"]}
                h_score = score_map.get(c["home"])
                a_score = score_map.get(c["away"])

                if h_score is None or a_score is None:
                    continue

                winner = c["home"] if h_score > a_score else c["away"]
                c["status"] = "WON" if c["pick"] == winner else "LOST"
                c["settled_at"] = datetime.utcnow().isoformat()

                if c["status"] == "WON":
                    profit = round((c["stake"] * c["odds"] * TAX_PL) - c["stake"], 2)
                    emoji = "✅"
                    result_txt = f"Zysk: <b>+{profit} zł</b>"
                else:
                    profit = -c["stake"]
                    emoji = "❌"
                    result_txt = f"Strata: <b>-{c['stake']} zł</b>"

                c["profit"] = profit

                msg = (
                    f"{emoji} <b>ROZLICZONO</b>\n"
                    f"{c['home']} - {c['away']}\n"
                    f"Wynik: {h_score}:{a_score}\n"
                    f"Typ: {c['pick']} @ {c['odds']}\n"
                    f"{result_txt}"
                )

                send_msg(msg)
                print(f"[OK] {c['home']} - {c['away']} | {c['status']}")

            except Exception as e:
                print(f"[ERROR] {c['home']} - {c['away']} | {e}")

    save_coupons(coupons)
    print("[SETTLE] Zapisano coupons_notax.json")


if __name__ == "__main__":
    run_settler()