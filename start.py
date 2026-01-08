import requests
import json
import os
from datetime import datetime, timedelta, timezone

# ================= CONFIG =================
DEBUG = True

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

COUPONS_FILE = "coupons.json"
BANKROLL_FILE = "bankroll.json"
META_FILE = "meta.json"

START_BANKROLL = 100.0
MAX_HOURS_AHEAD = 72

# ======= PROGI =======
VALUE_THRESHOLD = 0.035
VALUE_THRESHOLD_NBA = 0.02

MIN_ODDS_SOCCER = 2.50
MIN_ODDS_NHL = 2.30
MIN_ODDS_NBA = 1.90
MAX_ODDS_NBA = 2.35

# ======= LIGI (TYLKO OBSŁUGIWANE) =======
LEAGUES = [
    "icehockey_nhl",
    "basketball_nba",
    "basketball_euroleague",
    "soccer_epl",
    "soccer_italy_serie_a",
    "soccer_italy_serie_b",
    "soccer_spain_la_liga",
    "soccer_france_ligue_one",
    "soccer_germany_bundesliga",
    "soccer_germany_bundesliga2",
    "soccer_uefa_champs_league"
]

# ================= TELEGRAM =================
def send_msg(text, target="types"):
    chat_id = T_CHAT_RESULTS if target == "results" else T_CHAT
    if not T_TOKEN or not chat_id:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "disable_web_page_preview": True
            },
            timeout=10
        )
    except:
        pass

# ================= BANKROLL =================
def ensure_bankroll_file():
    if not os.path.exists(BANKROLL_FILE):
        with open(BANKROLL_FILE, "w") as f:
            json.dump({"bankroll": START_BANKROLL}, f)

def load_bankroll():
    try:
        with open(BANKROLL_FILE) as f:
            return json.load(f).get("bankroll", START_BANKROLL)
    except:
        return START_BANKROLL

# ================= SCAN OFFERS (DEBUG) =================
def scan_offers():
    total_scanned = 0
    total_selected = 0

    working_leagues = []
    dead_leagues = []

    for league in LEAGUES:
        league_ok = False

        for key in API_KEYS:
            try:
                url = f"https://api.the-odds-api.com/v4/sports/{league}/odds"
                r = requests.get(url, params={"apiKey": key}, timeout=10)

                if DEBUG:
                    print(f"[DEBUG] Liga={league} | Klucz={key[:5]}*** | Status={r.status_code}")

                if r.status_code != 200:
                    continue

                data = r.json()
                league_ok = True
                working_leagues.append(league)
                total_scanned += len(data)

                if DEBUG:
                    print(f"[DEBUG]  ↳ zwrócono {len(data)} meczów")

                for game in data:
                    odds = game.get("odds", 0)
                    edge = game.get("edge", 0)

                    passed = False

                    if league == "basketball_nba":
                        passed = MIN_ODDS_NBA <= odds <= MAX_ODDS_NBA and edge >= VALUE_THRESHOLD_NBA
                    elif "soccer" in league:
                        passed = odds >= MIN_ODDS_SOCCER and edge >= VALUE_THRESHOLD
                    elif "icehockey" in league:
                        passed = odds >= MIN_ODDS_NHL and edge >= VALUE_THRESHOLD
                    else:
                        passed = edge >= VALUE_THRESHOLD

                    if passed:
                        total_selected += 1

                break

            except Exception as e:
                if DEBUG:
                    print(f"[DEBUG] ERROR liga={league}: {e}")

        if not league_ok:
            dead_leagues.append(league)

    # ======= DEBUG PODSUMOWANIE =======
    if DEBUG:
        print("========== DEBUG SUMMARY ==========")
        print("DZIAŁAJĄCE LIGI:", working_leagues)
        print("NIEDOSTĘPNE LIGI:", dead_leagues)
        print("ZESKANOWANE MECZE:", total_scanned)
        print("WYBRANE TYPY:", total_selected)

    send_msg(
        f"🔍 Skanowanie ofert\n"
        f"━━━━━━━━━━━━━━\n"
        f"Zeskanowano: {total_scanned} meczów\n"
        f"Wybrano: {total_selected} typów\n\n"
        f"✅ Działa: {len(working_leagues)} lig\n"
        f"❌ Niedostępne: {len(dead_leagues)} lig",
        "results"
    )

# ================= RUN =================
def run():
    ensure_bankroll_file()
    scan_offers()

if __name__ == "__main__":
    run()