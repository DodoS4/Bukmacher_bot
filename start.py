import requests
import json
from datetime import datetime, timedelta
import os

# ================= KONFIG =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")
API_KEYS = [
    os.getenv("ODDS_KEY"),
    os.getenv("ODDS_KEY_2"),
    os.getenv("ODDS_KEY_3"),
    os.getenv("ODDS_KEY_4"),
    os.getenv("ODDS_KEY_5")
]
COUPON_FILE = "coupons.json"
MAX_HOURS_AHEAD = 48

# ================= FUNKCJE =================
def get_upcoming_matches(api_key):
    url = f"https://api.example.com/odds/upcoming"  # <-- wstaw prawdziwy endpoint
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        return resp.json()  # zakładamy listę meczów z kluczami: league, home, away, odds_home, odds_away, date
    except Exception as e:
        print(f"API error: {e}")
        return []

def rotate_keys(keys):
    for key in keys:
        matches = get_upcoming_matches(key)
        if matches:
            return matches
    return []

def filter_matches(matches):
    now = datetime.utcnow()
    future_limit = now + timedelta(hours=MAX_HOURS_AHEAD)
    filtered = []
    for m in matches:
        try:
            match_date = datetime.fromisoformat(m["date"].replace("Z", "+00:00"))
            if now <= match_date <= future_limit:
                filtered.append(m)
        except Exception as e:
            print("Błąd parsowania daty:", e)
    return filtered

def classify_match(match):
    """
    Prosta logika VALUE / PEWNIAK:
    Kurs < 1.6 -> PEWNIAK
    Kurs >= 1.6 -> VALUE
    """
    odds = match.get("odds_home", 1.5)
    pick_type = "PEWNIAK" if odds < 1.6 else "VALUE"
    return pick_type

def format_coupon(match):
    pick = classify_match(match)
    match_date = datetime.fromisoformat(match["date"].replace("Z", "+00:00"))
    return (
        f"🏀 {match['league']}\n"
        f"{match['home']} 🆚 {match['away']}\n"
        f"🎯 Typ: {match['home']} ({pick})\n"
        f"💸 Kurs: {match.get('odds_home',1.5)} | ⏳ Pending\n"
        f"📅 {match_date.strftime('%d.%m.%Y %H:%M')}"
    )

def send_telegram(message):
    if not T_TOKEN or not T_CHAT:
        print("Brak T_TOKEN lub T_CHAT")
        return
    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
    try:
        resp = requests.post(url, data={"chat_id": T_CHAT, "text": message, "parse_mode":"Markdown"})
        if resp.status_code != 200:
            print("Błąd Telegram:", resp.text)
    except Exception as e:
        print("Wyjątek Telegram:", e)

def save_coupons(coupons):
    try:
        if os.path.exists(COUPON_FILE):
            with open(COUPON_FILE, "r", encoding="utf-8") as f:
                existing = json.load(f)
        else:
            existing = []
        existing.extend(coupons)
        with open(COUPON_FILE, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print("Błąd zapisu pliku:", e)

# ================= MAIN =================
def main():
    print("Pobieranie nadchodzących meczów...")
    matches = rotate_keys(API_KEYS)
    if not matches:
        print("Brak meczów lub problem z API")
        return

    matches = filter_matches(matches)
    coupons = []
    for m in matches:
        try:
            msg = format_coupon(m)
            send_telegram(msg)
            print(msg)
            print("──────────────────────")
            coupons.append({
                "league": m["league"],
                "home": m["home"],
                "away": m["away"],
                "pick": classify_match(m),
                "odds": m.get("odds_home", 1.5),
                "date": m["date"]
            })
        except Exception as e:
            print("Błąd przetwarzania meczu:", e)

    save_coupons(coupons)
    print(f"Zapisano {len(coupons)} kuponów do {COUPON_FILE}")

if __name__ == "__main__":
    main()