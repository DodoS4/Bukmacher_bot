import requests
import json
from datetime import datetime, timedelta
import os

# ================= KONFIGURACJA =================
API_KEYS = [
    os.getenv("ODDS_KEY"),
    os.getenv("ODDS_KEY_2"),
    os.getenv("ODDS_KEY_3"),
    os.getenv("ODDS_KEY_4"),
    os.getenv("ODDS_KEY_5")
]

T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")

COUPON_FILE = "coupons.json"
MAX_HOURS_AHEAD = 48

# Zakres kursów
MIN_ODDS_DEFAULT = 1.55
MAX_ODDS_DEFAULT = 2.05
LEAGUE_ODDS = {
    "basketball_nba": 2.20,
    "hockey_nhl": 2.20
}

# Stake
STAKE_MIN = 0.015   # 1.5% BR
STAKE_MAX = 0.02    # 2% BR
BANKROLL = 1000     # startowy bankroll, dynamiczny w stats

# ================= FUNKCJE =================
def send_telegram(message):
    if not T_TOKEN or not T_CHAT:
        print("[WARN] Brak T_TOKEN lub T_CHAT – telegram wyłączony")
        return
    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
    try:
        resp = requests.post(url, data={"chat_id": T_CHAT, "text": message})
        if resp.status_code != 200:
            print(f"[WARN] Telegram: {resp.status_code} | {resp.text}")
    except Exception as e:
        print(f"[ERROR] Telegram: {e}")

def get_upcoming_matches(key, sport):
    url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/?apiKey={key}&regions=eu&markets=h2h"
    try:
        print(f"[DEBUG] Pobieram {sport} dla klucza {key}")
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except requests.HTTPError as e:
        print(f"[ERROR] {sport} | {e} | {e.response.text}")
    except requests.RequestException as e:
        print(f"[ERROR] {sport} | Błąd połączenia | {e}")
    return []

def filter_matches(matches, league):
    filtered = []
    now = datetime.utcnow()
    max_time = now + timedelta(hours=MAX_HOURS_AHEAD)
    for m in matches:
        try:
            match_time = datetime.fromisoformat(m["commence_time"].replace("Z", "+00:00"))
            if now <= match_time <= max_time:
                # filtr kursów
                max_odds = LEAGUE_ODDS.get(league, MAX_ODDS_DEFAULT)
                outcomes = m["bookmakers"][0]["markets"][0]["outcomes"]
                valid_outcomes = [o for o in outcomes if MIN_ODDS_DEFAULT <= o["price"] <= max_odds]
                if valid_outcomes:
                    filtered.append({
                        "league": m.get("sport_title"),
                        "sport_key": league,
                        "home_team": m.get("home_team"),
                        "away_team": m.get("away_team"),
                        "commence_time": match_time.isoformat(),
                        "odds": valid_outcomes
                    })
        except Exception as e:
            print(f"[WARN] Problem z datą meczu: {m.get('home_team')} vs {m.get('away_team')} | {e}")
    return filtered

def calculate_stake(bankroll, conservative=True):
    pct = STAKE_MIN if conservative else STAKE_MAX
    return round(bankroll * pct, 2)

def main():
    leagues = ["basketball_nba", "hockey_nhl"]  # dodaj inne ligi jeśli chcesz
    all_matches = []

    for league in leagues:
        for key in API_KEYS:
            matches = get_upcoming_matches(key, league)
            if matches:
                filtered = filter_matches(matches, league)
                print(f"[INFO] {league} | Klucz {key} pobrał {len(filtered)} ważnych meczów.")
                all_matches.extend(filtered)

    # anty-duplikaty
    unique_matches = []
    seen = set()
    for m in all_matches:
        identifier = (m["home_team"], m["away_team"], m["commence_time"])
        if identifier not in seen:
            seen.add(identifier)
            unique_matches.append(m)

    if unique_matches:
        print(f"[INFO] Łącznie unikalnych ważnych meczów: {len(unique_matches)}")
        with open(COUPON_FILE, "w", encoding="utf-8") as f:
            json.dump(unique_matches, f, ensure_ascii=False, indent=4)
        # Wyślij na Telegram
        for m in unique_matches:
            for outcome in m["odds"]:
                msg = (
                    f"🏀 {m['league']}\n"
                    f"{m['home_team']} 🆚 {m['away_team']}\n"
                    f"🎯 Typ: {outcome['name']}\n"
                    f"💸 Kurs: {outcome['price']} | ⏳ Pending\n"
                    f"📅 {datetime.fromisoformat(m['commence_time']).strftime('%d.%m.%Y %H:%M')}"
                )
                send_telegram(msg)
        print("[INFO] Mecze wysłane na Telegram")
    else:
        print("[WARN] Brak ważnych meczów do zapisania.")

if __name__ == "__main__":
    main()