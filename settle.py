import requests, json, os
from datetime import datetime, timezone

# ================= CONFIG =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS")
API_KEY = os.getenv("ODDS_KEY")

COUPONS_FILE = "coupons_notax.json"
TAX_PL = 1.0  # NO TAX

# ================= HELPERS =================
def send_msg(txt):
    if not T_TOKEN or not T_CHAT_RESULTS:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
            json={"chat_id": T_CHAT_RESULTS, "text": txt, "parse_mode": "HTML"}
        )
    except Exception as e:
        print(f"⚠️ Telegram error: {e}")

# ================= MAIN =================
def run_settler():
    if not os.path.exists(COUPONS_FILE):
        print("Brak pliku kuponów.")
        return

    with open(COUPONS_FILE, "r", encoding="utf-8") as f:
        coupons = json.load(f)

    pending = [
        c for c in coupons
        if c.get("status") == "PENDING" or
           (c.get("status") in ("WON", "LOST") and not c.get("notified", False))
    ]

    if not pending:
        print("Brak kuponów do rozliczenia.")
        return

    leagues = {c["league_key"] for c in pending}

    for l_key in leagues:
        url = f"https://api.the-odds-api.com/v4/sports/{l_key}/scores/"
        r = requests.get(url, params={"apiKey": API_KEY, "daysFrom": 3})

        if r.status_code != 200:
            continue

        scores = r.json()

        for c in coupons:
            if c.get("league_key") != l_key:
                continue

            if c.get("status") not in ("PENDING", "WON", "LOST"):
                continue

            if c.get("notified", False):
                continue

            match = next(
                (s for s in scores if s["home_team"] == c["home"] or s["away_team"] == c["home"]),
                None
            )

            if not match or not match.get("completed"):
                continue

            try:
                s_dict = {s["name"]: int(s["score"]) for s in match["scores"]}
                h = s_dict.get(c["home"])
                a = s_dict.get(c["away"])
                if h is None or a is None:
                    continue

                winner = c["home"] if h > a else c["away"]
                c["status"] = "WON" if c["pick"] == winner else "LOST"
                c["settled_at"] = datetime.now(timezone.utc).isoformat()

                if c["status"] == "WON":
                    profit = (c["stake"] * c["odds"] * TAX_PL) - c["stake"]
                    emoji = "✅"
                    res = f"Zysk: <b>+{profit:.2f} zł</b>"
                else:
                    emoji = "❌"
                    res = f"Strata: <b>-{c['stake']} zł</b>"

                msg = (
                    f"{emoji} <b>ROZLICZONO</b>\n"
                    f"{c['home']} - {c['away']}\n"
                    f"Wynik: {h}:{a}\n"
                    f"Typ: {c['pick']}\n"
                    f"{res}"
                )

                send_msg(msg)
                c["notified"] = True   # 🔐 BLOKADA DUBLI

                print(f"✔ Rozliczono: {c['home']} - {c['away']} ({c['status']})")

            except Exception as e:
                print(f"⚠️ Błąd rozliczenia: {e}")
                continue

    with open(COUPONS_FILE, "w", encoding="utf-8") as f:
        json.dump(coupons, f, indent=2)

    print("✅ Settler zakończony.")

if __name__ == "__main__":
    run_settler()