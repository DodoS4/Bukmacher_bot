import requests
import os
from datetime import datetime, timezone

# ================= CONFIG =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")

API_KEY = os.getenv("ODDS_KEY")

LEAGUES = [
    "icehockey_nhl",
    "basketball_nba",
    "soccer_epl",
]

# ================= TELEGRAM =================
def send_msg(text):
    if not T_TOKEN or not T_CHAT:
        print("Brak tokena lub chat_id!")
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
            json={
                "chat_id": T_CHAT,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            },
            timeout=10
        )
    except Exception as e:
        print("Błąd Telegram:", e)

# ================= ODDS =================
def fetch_matches():
    now = datetime.now(timezone.utc)
    for league in LEAGUES:
        try:
            r = requests.get(
                f"https://api.the-odds-api.com/v4/sports/{league}/odds",
                params={"apiKey": API_KEY, "markets":"h2h","regions":"eu"},
                timeout=10
            )
            if r.status_code != 200:
                print(f"{league} - Błąd API:", r.status_code)
                continue

            data = r.json()
            if not data:
                print(f"{league} - brak meczów")
                continue

            for match in data:
                home = match["home_team"]
                away = match["away_team"]
                dt = match["commence_time"]
                odds = {}
                for bm in match["bookmakers"]:
                    for m in bm["markets"]:
                        if m["key"] == "h2h":
                            for o in m["outcomes"]:
                                odds[o["name"]] = max(odds.get(o["name"],0), o["price"])
                msg = f"📌 {league} | {home} vs {away}\n🕒 {dt}\nOdds: {odds}"
                print(msg)
                send_msg(msg)
        except Exception as e:
            print("Błąd fetch_matches:", e)

if __name__ == "__main__":
    fetch_matches()