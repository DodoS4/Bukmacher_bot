import requests
import json
import os
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from dateutil import parser

# ================= CONFIG =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")

NO_TAX = True
TAX_PL = 1.0 if NO_TAX else 0.88

MIN_EDGE = 0.005       # 0.5%
STAKE = 100            # zł
SCAN_HOURS = 45        # ile godzin do przodu skanować

COUPONS_FILE = "coupons_notax.json"

API_KEYS = [os.getenv(f"ODDS_KEY{i}") for i in ["", "_2", "_3", "_4", "_5"]]
API_KEYS = [k for k in API_KEYS if k]

# ================= LIGI =================
LEAGUES = {
    # 🏀 KOSZYKÓWKA
    "basketball_nba": "🏀 NBA",
    "basketball_euroleague": "🏀 Euroleague",
    "basketball_spain_liga_acb": "🏀 Liga ACB",
    "basketball_france_lnb": "🏀 Francja LNB",

    # 🏒 HOKEJ
    "icehockey_nhl": "🏒 NHL",
    "icehockey_sweden_allsvenskan": "🏒 Allsvenskan",

    # ⚽ PIŁKA
    "soccer_poland_ekstraklasa": "⚽ Ekstraklasa",
    "soccer_germany_bundesliga2": "⚽ Bundesliga 2",
    "soccer_england_championship": "⚽ Championship",

    # 🎾 TENIS
    "tennis_atp_challenger_tour": "🎾 ATP Challenger",
    "tennis_wta_1000": "🎾 WTA 1000",
}

# ================= HELPERS =================
def send_msg(txt):
    if not T_TOKEN or not T_CHAT:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
            json={"chat_id": T_CHAT, "text": txt, "parse_mode": "HTML"}
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

def fetch_odds(league_key):
    for key in API_KEYS:
        r = requests.get(
            f"https://api.the-odds-api.com/v4/sports/{league_key}/odds",
            params={
                "apiKey": key,
                "markets": "h2h",
                "regions": "eu"
            }
        )
        if r.status_code == 200:
            return r.json()
    return []

# ================= MAIN =================
def run():
    print("[DEBUG] START SCAN")
    coupons = load_coupons()

    existing = {
        f"{c['home']}_{c['pick']}_{c['date']}"
        for c in coupons
    }

    now = datetime.now(timezone.utc)
    sent = 0

    for l_key, l_name in LEAGUES.items():
        events = fetch_odds(l_key)
        if not events:
            print(f"[DEBUG] {l_name}: brak wydarzeń")
            continue

        for e in events:
            home = e["home_team"]
            away = e["away_team"]
            dt = parser.isoparse(e["commence_time"])

            if not (now <= dt <= now + timedelta(hours=SCAN_HOURS)):
                continue

            odds_map = defaultdict(list)
            for bm in e.get("bookmakers", []):
                for m in bm.get("markets", []):
                    for o in m.get("outcomes", []):
                        odds_map[o["name"]].append(o["price"])

            best_odds = {
                team: max(prices)
                for team, prices in odds_map.items()
                if len(prices) >= 2
            }

            if len(best_odds) != 2:
                print(f"[DEBUG] REJECT BOOKS | {home}-{away}")
                continue

            inv = {k: 1/v for k, v in best_odds.items()}
            s = sum(inv.values())
            probs = {k: v/s for k, v in inv.items()}

            for pick, prob in probs.items():
                odds = best_odds[pick]
                edge = prob - (1 / (odds * TAX_PL))

                uid = f"{home}_{pick}_{dt.isoformat()}"
                if uid in existing:
                    continue

                if edge >= MIN_EDGE:
                    local_dt = dt.astimezone(timezone(timedelta(hours=1)))
                    date_str = local_dt.strftime("%d.%m %H:%M")

                    msg = (
                        f"🎯 <b>OKAZJA ({l_name})</b>\n"
                        f"{home} vs {away}\n"
                        f"⏰ {date_str}\n\n"
                        f"Typ: <b>{pick}</b>\n"
                        f"Kurs: <b>{odds}</b> (NO TAX)\n"
                        f"Edge: <b>+{edge*100:.2f}%</b>\n"
                        f"Stawka: <b>{STAKE} zł</b>"
                    )
                    send_msg(msg)

                    coupons.append({
                        "home": home,
                        "away": away,
                        "pick": pick,
                        "odds": odds,
                        "stake": STAKE,
                        "status": "PENDING",
                        "league_key": l_key,
                        "league_name": l_name,
                        "date": dt.isoformat(),
                        "edge": round(edge*100, 2)
                    })

                    existing.add(uid)
                    sent += 1

                    print(f"[DEBUG] ACCEPT {l_name} | {home}-{away} | {pick} | {odds} | EDGE {edge*100:.2f}%")
                else:
                    print(f"[DEBUG] REJECT EDGE {edge*100:.2f}% < {MIN_EDGE*100:.2f}% | {home}-{away} | {pick}")

    save_coupons(coupons)
    print(f"[DEBUG] SCAN COMPLETE | SENT: {sent}")

if __name__ == "__main__":
    run()