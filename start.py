import requests
import json
import os
from datetime import datetime, timedelta, timezone
from dateutil import parser

# ================= CONFIG =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")

API_KEYS = [
    os.getenv("ODDS_KEY"),
    os.getenv("ODDS_KEY_2"),
    os.getenv("ODDS_KEY_3"),
    os.getenv("ODDS_KEY_4"),
    os.getenv("ODDS_KEY_5"),
]

COUPONS_FILE = "coupons.json"
BOOKMAKER = "pinnacle"

MAX_HOURS = 48
STAKE = 50
VALUE_EDGE = 0.04
SURE_ODDS_MAX = 1.75

LEAGUES = {
    "basketball_nba": "🏀 NBA",
    "basketball_euroleague": "🏀 Euroleague",
    "icehockey_nhl": "🏒 NHL",
    "soccer_epl": "⚽ Premier League",
    "soccer_laliga": "⚽ La Liga",
    "soccer_serie_a": "⚽ Serie A",
    "soccer_bundesliga": "⚽ Bundesliga",
    "soccer_ligue_1": "⚽ Ligue 1",
    "soccer_champions_league": "⚽ Champions League",
    "soccer_europa_league": "⚽ Europa League",
}

# ================= UTILS =================
def send(msg):
    requests.post(
        f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
        json={"chat_id": T_CHAT, "text": msg, "parse_mode": "HTML"},
        timeout=10,
    )

def load():
    if not os.path.exists(COUPONS_FILE):
        return []
    return json.load(open(COUPONS_FILE, "r", encoding="utf-8"))

def save(data):
    json.dump(data, open(COUPONS_FILE, "w", encoding="utf-8"), indent=2, ensure_ascii=False)

# ================= MAIN =================
def main():
    now = datetime.now(timezone.utc)
    limit = now + timedelta(hours=MAX_HOURS)

    coupons = load()
    ids = {c["id"] for c in coupons}
    added = 0

    for league, name in LEAGUES.items():
        for key in API_KEYS:
            if not key:
                continue

            r = requests.get(
                f"https://api.the-odds-api.com/v4/sports/{league}/odds",
                params={
                    "apiKey": key,
                    "regions": "eu",
                    "markets": "h2h",
                    "oddsFormat": "decimal",
                },
                timeout=15,
            )

            if r.status_code != 200:
                continue

            for g in r.json():
                start = parser.isoparse(g["commence_time"])
                if not now <= start <= limit:
                    continue

                home, away = g["home_team"], g["away_team"]
                pin = next((b for b in g["bookmakers"] if b["key"] == BOOKMAKER), None)
                if not pin:
                    continue

                for o in pin["markets"][0]["outcomes"]:
                    odds = o["price"]
                    prob = 1 / odds
                    true_prob = prob * 1.05
                    edge = round(true_prob - prob, 4)

                    bet_type = None
                    if edge >= VALUE_EDGE:
                        bet_type = "VALUE"
                    elif odds <= SURE_ODDS_MAX:
                        bet_type = "SURE"
                    else:
                        continue

                    cid = f"{league}|{home}|{away}|{o['name']}|{start.isoformat()}"
                    if cid in ids:
                        continue

                    coupon = {
                        "id": cid,
                        "league": name,
                        "home": home,
                        "away": away,
                        "pick": o["name"],
                        "odds": odds,
                        "edge": edge,
                        "type": bet_type,
                        "stake": STAKE,
                        "status": "pending",
                        "date": start.isoformat(),
                    }

                    coupons.append(coupon)
                    ids.add(cid)
                    added += 1

                    send(
                        f"{name}\n"
                        f"{home} 🆚 {away}\n"
                        f"🎯 Typ: <b>{o['name']}</b> ({bet_type})\n"
                        f"💸 Kurs: <b>{odds}</b> | ⏳ Pending\n"
                        f"📅 {start.astimezone().strftime('%d.%m.%Y %H:%M')}"
                    )

    save(coupons)
    send(f"📊 <b>Skan zakończony</b>\n📌 Nowe kupony: {added}")

if __name__ == "__main__":
    main()