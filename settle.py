import requests, json, os
from datetime import datetime, timezone

T_TOKEN = os.getenv("T_TOKEN")
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS")
API_KEYS = [os.getenv(f"ODDS_KEY{i}") for i in ["", "_2", "_3", "_4", "_5"]]
API_KEYS = [k for k in API_KEYS if k]
COUPONS_FILE = "coupons_notax.json"
TAX_PL = 1.0  # NO TAX

def send_msg(txt):
    if not T_TOKEN or not T_CHAT_RESULTS:
        return
    try:
        requests.post(f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
                      json={"chat_id": T_CHAT_RESULTS, "text": txt, "parse_mode": "HTML"})
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

def fetch_scores(league_key):
    for key in API_KEYS:
        r = requests.get(f"https://api.the-odds-api.com/v4/sports/{league_key}/scores/",
                         params={"apiKey": key, "daysFrom": 3})
        if r.status_code == 200:
            return r.json()
    return []

def run_settler():
    coupons = load_coupons()
    pending = [c for c in coupons if c.get("status") == "PENDING"]
    if not pending:
        print("[SETTLE] Brak pending zakładów")
        return

    leagues = {c["league_key"] for c in pending}

    for l_key in leagues:
        scores = fetch_scores(l_key)
        print(f"[SETTLE] {l_key} | API games: {len(scores)}")

        for c in coupons:
            if c.get("status") != "PENDING" or c["league_key"] != l_key:
                continue

            # Szukamy meczu w danych z API
            match_score = next((s for s in scores if (s["home_team"] == c["home"] and s["away_team"] == c["away"]) or
                                                     (s["home_team"] == c["away"] and s["away_team"] == c["home"])), None)

            if not match_score:
                print(f"[PENDING] Brak wyniku w API: {c['home']} - {c['away']}")
                continue

            if not match_score.get("completed"):
                print(f"[PENDING] Mecz nie zakończony: {c['home']} - {c['away']}")
                continue

            try:
                s_dict = {s["name"]: int(s["score"]) for s in match_score["scores"]}
                h_score = s_dict.get(c["home"])
                a_score = s_dict.get(c["away"])
                if h_score is None or a_score is None:
                    continue

                winner = c["home"] if h_score > a_score else c["away"]
                c["status"] = "WON" if c["pick"] == winner else "LOST"
                c["settled_at"] = datetime.now(timezone.utc).isoformat()
                c["profit"] = round((c["stake"] * c["odds"] * TAX_PL) - c["stake"],2) if c["status"]=="WON" else -c["stake"]

                emoji = "✅" if c["status"] == "WON" else "❌"
                res_txt = f"Zysk: <b>+{c['profit']} zł</b>" if c["status"]=="WON" else f"Strata: <b>-{c['stake']} zł</b>"

                txt = (f"{emoji} <b>ROZLICZONO: {c['home']} - {c['away']}</b>\n"
                       f"Wynik: {h_score}:{a_score}\n"
                       f"Typ: {c['pick']} | {res_txt}")
                send_msg(txt)
                print(f"[DEBUG] Rozliczono {c['home']} - {c['away']} | {c['pick']} | {c['status']}")
            except Exception as e:
                print(f"[ERROR] {c['home']} - {c['away']} | {e}")
                continue

    with open(COUPONS_FILE, "w", encoding="utf-8") as f:
        json.dump(coupons, f, indent=2)
    print(f"[SETTLE] Zapisano {COUPONS_FILE}")


if __name__ == "__main__":
    run_settler()