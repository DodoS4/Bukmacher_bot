import requests
import json
import os
from datetime import datetime, timedelta, timezone

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

COUPONS_FILE = "coupons.json"
BANKROLL_FILE = "bankroll.json"
META_FILE = "meta.json"
START_BANKROLL = 100.0
MAX_HOURS_AHEAD = 72  # okno 72h

# ================= FILE UTILS =================
def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

# ================= BANKROLL =================
def ensure_bankroll_file():
    if not os.path.exists(BANKROLL_FILE):
        save_json(BANKROLL_FILE, {"bankroll": START_BANKROLL})

def load_bankroll():
    return load_json(BANKROLL_FILE, {}).get("bankroll", START_BANKROLL)

def save_bankroll(val):
    save_json(BANKROLL_FILE, {"bankroll": round(val, 2)})

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
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            },
            timeout=10
        )
    except:
        pass

# ================= GET WORKING LEAGUES =================
def get_working_leagues(key):
    try:
        r = requests.get("https://api.the-odds-api.com/v4/sports/", params={"apiKey": key}, timeout=10)
        if r.status_code == 200:
            data = r.json()
            return [l['key'] for l in data]
    except:
        pass
    return []

# ================= SCAN OFFERS – TEST BEZ FILTRÓW =================
def scan_offers():
    total_scanned = 0
    total_selected = 0
    working_leagues = []
    unavailable_leagues = []

    for league in ALL_LEAGUES:
        league_available = False
        for key in API_KEYS:
            try:
                r = requests.get(
                    f"https://api.the-odds-api.com/v4/sports/{league}/odds",
                    params={"apiKey": key, "daysFrom": MAX_HOURS_AHEAD},
                    timeout=10
                )
                if r.status_code == 200:
                    data = r.json()
                    total_scanned += len(data)
                    total_selected += len(data)  # Wszystkie mecze wybieramy w teście
                    league_available = True
                    break
            except:
                continue
        if league_available:
            working_leagues.append(league)
        else:
            unavailable_leagues.append(league)

    # Wysyłamy raport
    msg = "🔍 Skanowanie ofert – BEZ FILTRÓW\n━━━━━━━━━━━━━━\n"
    for lg in working_leagues:
        msg += f"✅ {lg}: dostępna\n"
    for lg in unavailable_leagues:
        msg += f"❌ {lg}: niedostępna\n"
    msg += f"\nZeskanowano: {total_scanned} meczów\nWybrano: {total_selected} value-betów\n"
    msg += f"\n✅ Działa: {len(working_leagues)} lig\n❌ Niedostępne: {len(unavailable_leagues)} lig"
    send_msg(msg, "results")
    print(msg)

# ================= MAIN =================
if __name__ == "__main__":
    # Lista wszystkich lig do testu – zmień lub dodaj swoje
    ALL_LEAGUES = [
        "icehockey_nhl",
        "basketball_nba",
        "basketball_euroleague",
        "soccer_epl",
        "soccer_efl_champ",
        "soccer_germany_bundesliga",
        "soccer_italy_serie_a",
        "soccer_spain_la_liga",
        "soccer_france_ligue_one",
        "soccer_uefa_champs_league"
    ]

    scan_offers()