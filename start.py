import requests
import json
from datetime import datetime, timedelta, timezone
import os

# ================= KONFIGURACJA =================
T_TOKEN = os.getenv("T_TOKEN")        # Telegram token
T_CHAT = os.getenv("T_CHAT")          # Telegram chat ID
API_KEYS = [
    os.getenv("ODDS_KEY"),
    os.getenv("ODDS_KEY_2"),
    os.getenv("ODDS_KEY_3"),
    os.getenv("ODDS_KEY_4"),
    os.getenv("ODDS_KEY_5")
]

COUPONS_FILE = "coupons.json"

# ================= FUNKCJE =================
def get_upcoming_matches(api_key):
    url = "https://api.example.com/odds/upcoming"  # zmień na prawdziwe endpointy
    headers = {"Authorization": f"Bearer {api_key}"}
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        print(f"API error {resp.status_code}")
        return []
    return resp.json()

def format_coupon(match, pick, odds, status="Pending"):
    league = match.get("league", "🏀 Unknown")
    date = datetime.fromisoformat(match["date"]).strftime("%d.%m.%Y %H:%M")
    value_type = match.get("value_type", "VALUE") if status == "Pending" else ""
    return (
        f"{league}\n"
        f"{match['home']} 🆚 {match['away']}\n"
        f"🎯 Typ: {pick} ({value_type})\n"
        f"💸 Kurs: {odds} | ⏳ {status}\n"
        f"📅 {date}"
    )

def send_telegram(message):
    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
    data = {"chat_id": T_CHAT, "text": message}
    requests.post(url, data=data)

# ================= GŁÓWNY SKAN =================
def main():
    all_matches = []
    for key in API_KEYS:
        matches = get_upcoming_matches(key)
        all_matches.extend(matches)

    now = datetime.now(timezone.utc)
    max_time = now + timedelta(hours=48)

    coupons = []

    for m in all_matches:
        match_time = datetime.fromisoformat(m["date"])
        if match_time > max_time:
            continue  # max 48h do przodu

        for pick in [m["home"], m["away"]]:
            odds_key = f"odds_{pick.lower().replace(' ', '_')}"
            odds = m.get(odds_key)
            if odds is None:
                continue  # brak kursu → pomijamy

            # określ Value lub Pewniak
            value_type = "VALUE" if m.get("edge", 0) > 1.0 else "SAFE"

            coupon = {
                "home": m["home"],
                "away": m["away"],
                "pick": pick,
                "odds": odds,
                "date": m["date"],
                "league": m.get("league", "🏀 Unknown"),
                "value_type": value_type,
                "status": "Pending"
            }
            coupons.append(coupon)

            # Wyślij na Telegram
            msg = format_coupon(coupon, pick, odds)
            send_telegram(msg)

    # Zapisz do pliku
    try:
        with open(COUPONS_FILE, "w", encoding="utf-8") as f:
            json.dump(coupons, f, ensure_ascii=False, indent=2)
        print(f"Zapisano {len(coupons)} kuponów do {COUPONS_FILE}")
    except Exception as e:
        print("Błąd zapisu kuponów:", e)

if __name__ == "__main__":
    main()