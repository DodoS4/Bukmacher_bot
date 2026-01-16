import requests
import json
import os
from datetime import datetime, timedelta, timezone

# ================= CONFIG =================
ODDS_KEY = os.getenv("ODDS_KEY")
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")

COUPON_FILE = "coupons.json"
MAX_HOURS = 48

SPORTS = {
    "soccer_epl": "⚽ Premier League",
}

# ================= TELEGRAM =================
def send_telegram(text):
    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
    payload = {
        "chat_id": T_CHAT,
        "text": text,
        "parse_mode": "HTML"
    }
    r = requests.post(url, json=payload, timeout=10)
    print("[TG]", r.status_code, r.text)

# ================= LOAD / SAVE =================
def load_coupons():
    if not os.path.exists(COUPON_FILE):
        return []
    with open(COUPON_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_coupons(data):
    with open(COUPON_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ================= API =================
def fetch_matches(sport):
    url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds"
    params = {
        "apiKey": ODDS_KEY,
        "regions": "eu",
        "markets": "h2h",
        "oddsFormat": "decimal"
    }
    r = requests.get(url, params=params, timeout=10)
    print("[API]", r.status_code, r.url)
    r.raise_for_status()
    return r.json()

# ================= MAIN =================
def main():
    now = datetime.now(timezone.utc)
    limit = now + timedelta(hours=MAX_HOURS)

    coupons = load_coupons()
    sent = 0

    for sport, league in SPORTS.items():
        matches = fetch_matches(sport)

        for m in matches:
            start = datetime.fromisoformat(
                m["commence_time"].replace("Z", "+00:00")
            )
            if not (now <= start <= limit):
                continue

            outcomes = m["bookmakers"][0]["markets"][0]["outcomes"]

            pick = max(outcomes, key=lambda x: x["price"])

            coupon = {
                "league": league,
                "home": m["home_team"],
                "away": m["away_team"],
                "pick": pick["name"],
                "odds": pick["price"],
                "date": start.isoformat(),
                "status": "pending"
            }

            coupons.append(coupon)

            msg = (
                f"{league}\n"
                f"{m['home_team']} 🆚 {m['away_team']}\n"
                f"🎯 Typ: {pick['name']}\n"
                f"💸 Kurs: {pick['price']}\n"
                f"📅 {start.strftime('%d.%m.%Y %H:%M')} UTC"
            )

            send_telegram(msg)
            sent += 1

    save_coupons(coupons)
    print(f"[DONE] Wysłano {sent} ofert")

if __name__ == "__main__":
    main()