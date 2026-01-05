import requests
import os
from datetime import datetime, timezone

# ===== KONFIG =====
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")
ODDS_KEY = os.getenv("ODDS_KEY")

SPORT = "soccer_epl"  # Premier League
REGION = "eu"
MARKET = "h2h"

# ===== TELEGRAM =====
def send_msg(text):
    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": T_CHAT,
        "text": text,
        "parse_mode": "Markdown"
    }, timeout=15)

# ===== POBIERANIE MECZÓW =====
def send_one_offer():
    url = f"https://api.the-odds-api.com/v4/sports/{SPORT}/odds/"
    params = {
        "apiKey": ODDS_KEY,
        "regions": REGION,
        "markets": MARKET,
        "oddsFormat": "decimal"
    }

    r = requests.get(url, params=params, timeout=15)
    games = r.json()

    if not games:
        send_msg("⚠️ Brak dostępnych meczów")
        return

    g = games[0]
    home = g["home_team"]
    away = g["away_team"]
    commence = datetime.fromisoformat(g["commence_time"].replace("Z", "+00:00"))

    bookmaker = g["bookmakers"][0]
    market = bookmaker["markets"][0]
    odds = {o["name"]: o["price"] for o in market["outcomes"]}

    home_odd = odds.get(home)
    if not home_odd:
        send_msg("⚠️ Brak kursu")
        return

    msg = (
        "🔥 *NOWA OFERTA*\n"
        "━━━━━━━━━━━━━━\n"
        f"⚽ {home} vs {away}\n"
        f"🕒 {commence.astimezone(timezone.utc).strftime('%d.%m %H:%M UTC')}\n"
        f"🎯 Typ: *{home} wygra*\n"
        f"💸 Kurs: `{home_odd}`"
    )

    send_msg(msg)

# ===== START =====
if __name__ == "__main__":
    send_one_offer()
