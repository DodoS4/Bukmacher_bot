import requests
import json
from datetime import datetime, timedelta

# ================= KONFIGURACJA =================
API_KEYS = [
    "TWÓJ_KLUCZ_1",
    "TWÓJ_KLUCZ_2",
    "TWÓJ_KLUCZ_3",
    "TWÓJ_KLUCZ_4",
    "TWÓJ_KLUCZ_5"
]

SPORTS = ["basketball_nba", "hockey_nhl", "soccer_epl", "soccer_spain_la_liga"]
COUPON_FILE = "coupons.json"
TELEGRAM_TOKEN = "<T_TOKEN>"
TELEGRAM_CHAT = "<T_CHAT>"

# Kursy
MIN_ODDS = 1.55
MAX_ODDS = 2.05
NBA_NHL_MAX = 2.20

# Maksymalny czas do meczu w godzinach
MAX_HOURS_AHEAD = 48

# ================= FUNKCJE =================
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": TELEGRAM_CHAT, "text": message, "parse_mode": "Markdown"})

def get_matches(sport, key):
    url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/?apiKey={key}&regions=eu&markets=h2h"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except requests.HTTPError as e:
        print(f"[ERROR] {sport} | {e}")
    except requests.RequestException as e:
        print(f"[ERROR] {sport} | {e}")
    return []

def filter_matches(matches, sport):
    filtered = []
    now = datetime.utcnow()
    max_time = now + timedelta(hours=MAX_HOURS_AHEAD)
    for m in matches:
        try:
            match_time = datetime.fromisoformat(m["commence_time"].replace("Z", "+00:00"))
            if not now <= match_time <= max_time:
                continue
            if not m.get("bookmakers"):
                continue
            market = m["bookmakers"][0]["markets"][0]["outcomes"][0]
            odds = market["price"]
            max_odds = NBA_NHL_MAX if sport in ["basketball_nba","hockey_nhl"] else MAX_ODDS
            if odds < MIN_ODDS or odds > max_odds:
                continue
            filtered.append({
                "sport": m["sport_title"],
                "home": m["home_team"],
                "away": m["away_team"],
                "time": match_time.isoformat(),
                "odds": odds,
                "pick": market["name"]
            })
        except Exception as e:
            print(f"[WARN] Problem z datą lub kursem: {m.get('home_team')} vs {m.get('away_team')} | {e}")
    return filtered

def main():
    all_matches = []
    for sport in SPORTS:
        for key in API_KEYS:
            matches = get_matches(sport, key)
            if matches:
                filtered = filter_matches(matches, sport)
                all_matches.extend(filtered)
                break  # jeśli klucz działa, nie próbujemy kolejnych

    # anty-duplikaty
    unique = {f"{m['home']}_{m['away']}_{m['time']}": m for m in all_matches}.values()

    if unique:
        with open(COUPON_FILE, "w", encoding="utf-8") as f:
            json.dump(list(unique), f, ensure_ascii=False, indent=4)
        for m in unique:
            send_telegram(f"🏀 {m['sport']}\n{m['home']} vs {m['away']}\n🎯 {m['pick']}\n💸 {m['odds']} | ⏳ Pending\n📅 {m['time']}")
        print(f"[INFO] Wysłano {len(unique)} ofert na Telegram")
    else:
        print("[INFO] Brak nowych ofert")

if __name__ == "__main__":
    main()