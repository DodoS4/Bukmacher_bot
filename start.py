import os
import requests
from datetime import datetime, timezone

# ================= CONFIG =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS")
API_KEYS = [k for k in [
    os.getenv("ODDS_KEY"),
    os.getenv("ODDS_KEY_2"),
    os.getenv("ODDS_KEY_3"),
    os.getenv("ODDS_KEY_4"),
    os.getenv("ODDS_KEY_5")
] if k]

MAX_HOURS_AHEAD = 72  # pobieramy mecze do 72h

# ================= TELEGRAM =================
def send_msg(text, target="types"):
    chat_id = T_CHAT_RESULTS if target == "results" else T_CHAT
    if not T_TOKEN or not chat_id:
        print(text)
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            },
            timeout=10
        )
    except Exception as e:
        print("Błąd wysyłki Telegram:", e)

# ================= TEST API =================
def test_api():
    key = API_KEYS[0]  # bierzemy pierwszy dostępny klucz
    print("🔍 Sprawdzanie dostępnych lig dla klucza API...")
    r = requests.get(f"https://api.the-odds-api.com/v4/sports", params={"apiKey": key}, timeout=10)
    if r.status_code != 200:
        print("❌ Nie udało się pobrać lig. Status:", r.status_code)
        return []
    leagues = r.json()
    for l in leagues:
        print(f"{l['key']} - {l['title']}")
    return [l["key"] for l in leagues]

# ================= SCAN MECCZY =================
def scan_offers():
    available_leagues = test_api()
    total_scanned = 0

    for league in available_leagues:
        league_scanned = False
        for key in API_KEYS:
            try:
                r = requests.get(
                    f"https://api.the-odds-api.com/v4/sports/{league}/odds",
                    params={"apiKey": key, "daysFrom": MAX_HOURS_AHEAD},
                    timeout=10
                )
                if r.status_code != 200:
                    continue
                data = r.json()
                league_scanned = True
                print(f"\n✅ {league}: {len(data)} meczów")
                for game in data:
                    home = game.get("home_team")
                    away = game.get("away_team")
                    print(f"   ➤ {home} vs {away}")
                total_scanned += len(data)
                break
            except Exception as e:
                print(f"❌ Błąd ligi {league}: {e}")
                continue
        if not league_scanned:
            print(f"❌ {league}: brak danych lub niedostępna")

    print("\n━━━━━━━━━━━━━━━━━━")
    print(f"Zeskanowano łącznie: {total_scanned} meczów")

# ================= RUN =================
if __name__ == "__main__":
    scan_offers()