import os
import requests
from datetime import datetime, timedelta, timezone
import json

# ================= CONFIG =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")
COUPONS_FILE = "coupons.json"
MAX_HOURS_AHEAD = 48

# ================= HELPERS =================
def fetch_matches():
    """
    Pobiera mecze z API (tu przykładowe dane statyczne).
    W produkcji podmień na prawdziwe API typu OddsAPI lub inny źródło.
    """
    # Przykładowe dane
    return [
        {
            "home": "Paris Basketball",
            "away": "AS Monaco",
            "odds_home": 1.54,
            "odds_away": 2.5,
            "edge_home": 2.5,
            "edge_away": -1.2,
            "league": "🏀 Euroleague",
            "date": (datetime.now(timezone.utc) + timedelta(hours=5)).isoformat()
        },
        {
            "home": "NBA Team A",
            "away": "NBA Team B",
            "odds_home": 1.21,
            "odds_away": 3.1,
            "edge_home": 0.3,
            "edge_away": 5.0,
            "league": "🏀 NBA",
            "date": (datetime.now(timezone.utc) + timedelta(hours=50)).isoformat()
        }
    ]

def save_coupons(coupons):
    with open(COUPONS_FILE, "w", encoding="utf-8") as f:
        json.dump(coupons, f, ensure_ascii=False, indent=2)

def send_telegram(message):
    if not T_CHAT or not T_TOKEN:
        print("Brak T_CHAT lub T_TOKEN – nie można wysłać kuponu")
        return
    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": T_CHAT, "text": message, "parse_mode": "HTML"})

def format_coupon(match, pick, type_label):
    date_obj = datetime.fromisoformat(match["date"])
    date_str = date_obj.strftime("%d.%m.%Y %H:%M")
    odds = match[f"odds_{pick.lower()}"]
    status = "⏳ Pending"
    return (
        f"{match['league']}\n"
        f"{match['home']} 🆚 {match['away']}\n"
        f"🎯 Typ: {pick} ({type_label})\n"
        f"💸 Kurs: {odds} | {status}\n"
        f"📅 {date_str}"
    )

# ================= MAIN =================
if __name__ == "__main__":
    matches = fetch_matches()
    now = datetime.now(timezone.utc)
    coupons = []

    for m in matches:
        match_date = datetime.fromisoformat(m["date"])
        if match_date > now + timedelta(hours=MAX_HOURS_AHEAD):
            continue  # Pomiń mecze >48h w przód

        # Wybór typu
        if m["edge_home"] > 1:
            pick = m["home"]
            type_label = "VALUE"
        elif m["edge_away"] > 1:
            pick = m["away"]
            type_label = "VALUE"
        else:
            # Pewniak – wybierz minimalny kurs
            pick = m["home"] if m["odds_home"] < m["odds_away"] else m["away"]
            type_label = "PEWNIAK"

        coupon = {
            "home": m["home"],
            "away": m["away"],
            "pick": pick,
            "odds": m[f"odds_{pick.lower()}"],
            "stake": 100,
            "status": "PENDING",
            "league": m["league"],
            "league_name": m["league"],
            "date": m["date"],
            "type": type_label
        }
        coupons.append(coupon)

        # Wyślij Telegram
        msg = format_coupon(m, pick, type_label)
        send_telegram(msg)

    save_coupons(coupons)
    print(f"📌 Dodano {len(coupons)} nowych kuponów.")