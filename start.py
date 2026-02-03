import os
import json
import requests
from datetime import datetime, timezone

# ================= KONFIG =================
COUPONS_FILE = "coupons.json"

STAKE = 100.0
MIN_ODDS = 2.20
MAX_ODDS = 10.00   # zabezpieczenie

DEBUG = True

SPORTS = {
    "icehockey_nhl": "🏒 NHL",
    "soccer_poland_ekstraklasa": "🇵🇱 Ekstraklasa",
    "soccer_italy_serie_a": "🇮🇹 Serie A",
    "soccer_spain_la_liga": "🇪🇸 La Liga",
    "soccer_germany_bundesliga": "🇩🇪 Bundesliga",
    "soccer_england_premier_league": "🏴 Premier League",
    "basketball_euroleague": "🏀 Euroleague"
}

# ================= POMOC =================
def debug(msg):
    if DEBUG:
        print(msg)

def get_secret(name):
    val = os.environ.get(name)
    return str(val).strip() if val else None

def get_all_api_keys():
    keys = []
    for i in range(1, 11):
        name = "ODDS_KEY" if i == 1 else f"ODDS_KEY_{i}"
        val = os.getenv(name)
        if val:
            keys.append(val)
    return keys

def get_odds(sport, keys):
    for key in keys:
        url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
        params = {
            "apiKey": key,
            "regions": "eu",
            "markets": "h2h",
            "oddsFormat": "decimal"
        }
        try:
            r = requests.get(url, params=params, timeout=15)
            if r.status_code == 200:
                debug(f"📡 Pobieranie kursów: {sport}")
                return r.json()
        except Exception as e:
            debug(f"❌ API error {sport}: {e}")
    return []

# ================= START =================
def start():
    print(f"\n🚀 START BOT: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}\n")

    keys = get_all_api_keys()
    if not keys:
        debug("❌ Brak API keys")
        return

    coupons = []
    if os.path.exists(COUPONS_FILE):
        coupons = json.load(open(COUPONS_FILE, "r", encoding="utf-8"))

    existing_ids = {c["id"] for c in coupons}

    new_coupons = 0

    for sport, label in SPORTS.items():
        debug(f"🔍 Skanowanie: {label}")

        events = get_odds(sport, keys)

        for e in events:
            eid = e.get("id")
            if not eid or eid in existing_ids:
                continue

            home = e.get("home_team")
            away = e.get("away_team")

            bookmakers = e.get("bookmakers", [])
            if not bookmakers:
                debug(f"⛔ Brak bookmakerów: {home} vs {away}")
                continue

            market = bookmakers[0]["markets"][0]
            outcomes = market.get("outcomes", [])

            if len(outcomes) != 2:
                debug(f"⛔ Nie czyste H2H (2 outcomes): {home} vs {away}")
                continue

            o1, o2 = outcomes

            # mapowanie drużyn
            if o1["name"] == home:
                home_odds = float(o1["price"])
                away_odds = float(o2["price"])
            elif o2["name"] == home:
                home_odds = float(o2["price"])
                away_odds = float(o1["price"])
            else:
                debug(f"⛔ Błędne mapowanie: {home} vs {away}")
                continue

            # gramy underdoga
            if home_odds >= MIN_ODDS:
                pick = home
                odds = home_odds
            elif away_odds >= MIN_ODDS:
                pick = away
                odds = away_odds
            else:
                debug(f"⛔ Brak kursu ≥ {MIN_ODDS}: {home} vs {away}")
                continue

            if odds > MAX_ODDS:
                debug(f"⛔ Kurs za wysoki ({odds}): {home} vs {away}")
                continue

            coupon = {
                "id": eid,
                "sport": sport,
                "home": home,
                "away": away,
                "outcome": pick,
                "odds": round(odds, 2),
                "stake": STAKE,
                "created_at": datetime.now(timezone.utc).isoformat()
            }

            coupons.append(coupon)
            existing_ids.add(eid)
            new_coupons += 1

            debug(f"🔥 UNDERDOG: {home} vs {away} → {pick} @ {odds}")

    json.dump(coupons, open(COUPONS_FILE, "w", encoding="utf-8"), indent=4)

    print("━━━━━━━━━━━━━━━━━━━━")
    print(f"🎯 Nowe typy: {new_coupons}")
    print(f"💰 Łączna stawka: {new_coupons * STAKE:.0f} PLN")

# ================= ENTRY =================
if __name__ == "__main__":
    start()
