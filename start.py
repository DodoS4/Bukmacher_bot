import os
import json
import requests
from datetime import datetime, timezone, timedelta

# ================= CONFIG =================
BASE_URL = "https://api.the-odds-api.com/v4"
REGIONS = "eu"
BOOKMAKERS = "bet365"
MARKETS = "h2h,totals,btts"
ODDS_FORMAT = "decimal"

COUPONS_FILE = "coupons.json"

# ================= LIGI (22) =================
LEAGUES = {
    # ⚽ FOOTBALL
    "soccer_epl": "🏴 Premier League",
    "soccer_germany_bundesliga": "🇩🇪 Bundesliga",
    "soccer_italy_serie_a": "🇮🇹 Serie A",
    "soccer_spain_la_liga": "🇪🇸 La Liga",
    "soccer_france_ligue_one": "🇫🇷 Ligue 1",
    "soccer_portugal_primeira_liga": "🇵🇹 Primeira Liga",
    "soccer_netherlands_eredivisie": "🇳🇱 Eredivisie",
    "soccer_austria_bundesliga": "🇦🇹 Bundesliga",
    "soccer_denmark_superliga": "🇩🇰 Superliga",
    "soccer_switzerland_superleague": "🇨🇭 Super League",
    "soccer_greece_super_league": "🇬🇷 Super League",
    "soccer_poland_ekstraklasa": "🇵🇱 Ekstraklasa",

    # 🏒 HOCKEY
    "icehockey_nhl": "🏒 NHL",
    "icehockey_sweden_hockeyallsvenskan": "🇸🇪 HockeyAllsvenskan",
    "icehockey_finland_liiga": "🇫🇮 Liiga",
    "icehockey_germany_del": "🇩🇪 DEL",
    "icehockey_switzerland_nla": "🇨🇭 NLA",
    "icehockey_czech_extraliga": "🇨🇿 Extraliga",
    "icehockey_slovakia_extraliga": "🇸🇰 Extraliga",
    "icehockey_denmark_metal_ligaen": "🇩🇰 Metal Ligaen",
    "icehockey_norway_eliteserien": "🇳🇴 Eliteserien"
}

# ================= API KEYS =================
def get_api_keys():
    keys = []
    for i in range(1, 11):
        name = "ODDS_KEY" if i == 1 else f"ODDS_KEY_{i}"
        val = os.getenv(name)
        if val:
            keys.append(val)
    return keys

# ================= FETCH =================
def fetch_odds(sport, keys):
    for key in keys:
        try:
            r = requests.get(
                f"{BASE_URL}/sports/{sport}/odds",
                params={
                    "apiKey": key,
                    "regions": REGIONS,
                    "markets": MARKETS,
                    "bookmakers": BOOKMAKERS,
                    "oddsFormat": ODDS_FORMAT
                },
                timeout=15
            )

            if r.status_code == 200:
                return r.json()

            print(f"⚠️ API {sport} status {r.status_code}")

        except Exception as e:
            print(f"❌ Request error {sport}: {e}")

    return []

# ================= FILTER =================
def is_valid_pick(sport, market, outcome, odds, point):
    if sport.startswith("soccer"):
        if market == "btts" and outcome == "Yes":
            return True
        if market == "totals" and outcome == "Over" and point in (2.5, 3.5):
            return True
        if market == "h2h" and odds >= 2.20:
            return True

    if sport.startswith("icehockey"):
        if market == "totals" and outcome == "Over" and point in (4.5, 5.5):
            return True
        if market == "h2h" and odds <= 2.40:
            return True

    return False

# ================= MAIN =================
def main():
    print(f"\n🚀 START BOT | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    api_keys = get_api_keys()
    if not api_keys:
        print("❌ Brak kluczy API")
        return

    coupons = []
    now = datetime.now(timezone.utc)
    future = now + timedelta(hours=48)

    for league, label in LEAGUES.items():
        print(f"🔍 Liga: {label}")
        matches = fetch_odds(league, api_keys)

        if not matches:
            print("❌ Brak danych")
            continue

        for match in matches:
            try:
                start = datetime.fromisoformat(
                    match["commence_time"].replace("Z", "+00:00")
                )
                if not (now < start < future):
                    continue
            except:
                continue

            for bookmaker in match.get("bookmakers", []):
                for market in bookmaker.get("markets", []):
                    for outcome in market.get("outcomes", []):

                        if not is_valid_pick(
                            league,
                            market["key"],
                            outcome["name"],
                            outcome["price"],
                            outcome.get("point")
                        ):
                            continue

                        coupons.append({
                            "id": match["id"],
                            "sport": league,
                            "home": match["home_team"],
                            "away": match["away_team"],
                            "market": market["key"],
                            "outcome": outcome["name"],
                            "odds": outcome["price"],
                            "stake": 100,
                            "time": match["commence_time"]
                        })

    with open(COUPONS_FILE, "w", encoding="utf-8") as f:
        json.dump(coupons, f, indent=4, ensure_ascii=False)

    print(f"🏁 KONIEC | Wysłane typy: {len(coupons)}")

# ================= ENTRY =================
if __name__ == "__main__":
    main()
