import os
import json
import time
import requests
from datetime import datetime, timezone

# ================== KONFIG ==================
COUPONS_FILE = "coupons.json"
KEY_INDEX_FILE = "key_index.txt"

SPORTS = {
    "icehockey_nhl": "🏒 NHL",
    "icehockey_sweden_allsvenskan": "🇸🇪 HockeyAllsvenskan",
    "icehockey_finland_liiga": "🇫🇮 Liiga",
    "icehockey_germany_del": "🇩🇪 DEL",
    "soccer_poland_ekstraklasa": "🇵🇱 Ekstraklasa"
}

ALLOWED_MARKETS = {
    "h2h",
    "totals",
    "btts",
    "double_chance"
}

MIN_ODDS = 1.40
MAX_ODDS = 3.50
MIN_VALUE = 2.0
MIN_BOOKMAKERS = 2

STAKE = 250

# ================== POMOCNICZE ==================
def get_secret(name):
    return os.getenv(name)

def send_telegram(msg):
    token = get_secret("T_TOKEN")
    chat = get_secret("T_CHAT")
    if not token or not chat:
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    requests.post(url, json={"chat_id": chat, "text": msg})

def load_keys():
    keys = []
    for i in range(1, 11):
        k = os.getenv("ODDS_KEY" if i == 1 else f"ODDS_KEY_{i}")
        if k:
            keys.append(k)
    return keys

def get_key_index():
    if not os.path.exists(KEY_INDEX_FILE):
        return 0
    return int(open(KEY_INDEX_FILE).read().strip() or 0)

def save_key_index(i):
    with open(KEY_INDEX_FILE, "w") as f:
        f.write(str(i))

def fetch_odds(sport, key):
    url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
    params = {
        "apiKey": key,
        "regions": "eu",
        "markets": ",".join(ALLOWED_MARKETS),
        "oddsFormat": "decimal"
    }
    r = requests.get(url, params=params, timeout=15)
    return r.json() if r.status_code == 200 else []

# ================== START ==================
def main():
    keys = load_keys()
    key_i = get_key_index()

    coupons = []
    if os.path.exists(COUPONS_FILE):
        coupons = json.load(open(COUPONS_FILE))

    log = []
    total_candidates = 0

    log.append(f"🚀 --- START BOT PRO: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} ---")

    for sport, label in SPORTS.items():
        key = keys[key_i % len(keys)]
        key_i += 1

        events = fetch_odds(sport, key)
        scanned = 0
        accepted = 0

        for ev in events:
            scanned += 1
            if not ev.get("bookmakers") or len(ev["bookmakers"]) < MIN_BOOKMAKERS:
                continue

            for bm in ev["bookmakers"]:
                for market in bm["markets"]:
                    if market["key"] not in ALLOWED_MARKETS:
                        continue

                    for o in market["outcomes"]:
                        odds = float(o.get("price", 0))
                        if odds < MIN_ODDS or odds > MAX_ODDS:
                            continue

                        # --- RYNKI ---
                        outcome = o["name"]
                        market_key = market["key"]

                        if market_key == "totals":
                            line = float(o.get("point", 0))
                            if line not in (4.5, 5.5):
                                continue
                            outcome = f"{outcome} {line}"

                        if market_key == "btts" and outcome != "Yes":
                            continue

                        if market_key == "double_chance" and outcome not in ("1X", "X2"):
                            continue

                        value = 2.5  # uproszczone value (placeholder)
                        if value < MIN_VALUE:
                            continue

                        coupon = {
                            "id": ev["id"],
                            "sport": sport,
                            "league": label,
                            "home": ev["home_team"],
                            "away": ev["away_team"],
                            "market_type": market_key,
                            "outcome": outcome,
                            "odds": odds,
                            "stake": STAKE,
                            "time": ev["commence_time"]
                        }

                        coupons.append(coupon)
                        accepted += 1
                        total_candidates += 1

                        icon = "🏒" if "icehockey" in sport else "⚽"
                        log.append(
                            f"{icon} {ev['home_team']} vs {ev['away_team']} — {outcome} ✅🔥"
                        )

        log.append(
            f"📊 {label} | API: {key_i} | ✅ kandydaci: {accepted}"
        )

    save_key_index(key_i)

    with open(COUPONS_FILE, "w") as f:
        json.dump(coupons, f, indent=4)

    log.append("━━━━━━━━━━━━━━━━")
    log.append(f"🎯 Nowe typy: {total_candidates}")
    log.append(f"💰 Łączna stawka: {total_candidates * STAKE} PLN")

    send_telegram("\n".join(log))


if __name__ == "__main__":
    main()
