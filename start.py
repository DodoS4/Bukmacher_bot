import requests
import json
import os
from datetime import datetime, timedelta, timezone
from dateutil import parser
import random

# ================= KONFIGURACJA =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS")

KEYS_POOL = [
    os.getenv("ODDS_KEY"),
    os.getenv("ODDS_KEY_2"),
    os.getenv("ODDS_KEY_3"),
    os.getenv("ODDS_KEY_4"),
    os.getenv("ODDS_KEY_5")
]
API_KEYS = [k for k in KEYS_POOL if k]

COUPONS_FILE = "coupons.json"
STAKE = 5.0
MAX_HOURS_AHEAD = 48

LEAGUES = [
    "soccer_epl",
    "soccer_spain_la_liga",
    "soccer_italy_serie_a",
    "soccer_germany_bundesliga",
    "soccer_france_ligue_one",
    "basketball_nba",
    "soccer_netherlands_eredivisie",
    "soccer_portugal_primeira_liga"
]

LEAGUE_INFO = {
    "soccer_epl": {"name": "Premier League", "flag": "🏴"},
    "soccer_spain_la_liga": {"name": "La Liga", "flag": "🇪🇸"},
    "soccer_italy_serie_a": {"name": "Serie A", "flag": "🇮🇹"},
    "soccer_germany_bundesliga": {"name": "Bundesliga", "flag": "🇩🇪"},
    "soccer_france_ligue_one": {"name": "Ligue 1", "flag": "🇫🇷"},
    "basketball_nba": {"name": "NBA", "flag": "🏀"},
    "soccer_netherlands_eredivisie": {"name": "Eredivisie", "flag": "🇳🇱"},
    "soccer_portugal_primeira_liga": {"name": "Primeira Liga", "flag": "🇵🇹"},
}

# ================= NARZĘDZIE ESCAPE =================
def escape_md(text):
    if not isinstance(text, str):
        return text
    return text.replace("_","\\_").replace("*","\\*").replace("[","\\[").replace("]","\\]").replace("`","\\`")

# ================= WYSYŁKA =================
def send_msg(text, target="types"):
    chat_id = T_CHAT_RESULTS if target=="results" else T_CHAT
    if not T_TOKEN:
        print("❌ Brak T_TOKEN w sekretach")
        return
    if not chat_id:
        print("❌ Brak chat_id w sekretach")
        return
    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode":"Markdown"}
    try:
        r = requests.post(url, json=payload, timeout=15)
        if r.status_code != 200:
            print(f"❌ Błąd Telegram API: {r.status_code} | {r.text}")
        else:
            print("✅ Wysłano wiadomość:", text[:50]+"...")
    except Exception as e:
        print("❌ Wyjątek przy wysyłaniu:", e)

# ================= COUPONS =================
def load_coupons():
    if os.path.exists(COUPONS_FILE):
        try:
            with open(COUPONS_FILE,"r",encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print("❌ Błąd wczytywania coupons.json:", e)
            return []
    return []

def save_coupons(coupons):
    with open(COUPONS_FILE,"w",encoding="utf-8") as f:
        json.dump(coupons[-500:], f, indent=4)

# ================= POBIERANIE MECZÓW =================
def get_upcoming_matches(league):
    matches = []
    if not API_KEYS:
        print("❌ Brak kluczy ODDS_KEY w sekretach")
        return matches
    for api_key in API_KEYS:
        try:
            url = f"https://api.the-odds-api.com/v4/sports/{league}/odds"
            params = {"apiKey": api_key, "regions":"eu","markets":"h2h","oddsFormat":"decimal"}
            r = requests.get(url, params=params, timeout=15)
            if r.status_code != 200:
                print(f"⚠️ Błąd API ({league}): {r.status_code}")
                continue
            data = r.json()
            for event in data:
                home = event["home_team"]
                away = event["away_team"]
                commence = event["commence_time"]
                if event.get("bookmakers"):
                    b = event["bookmakers"][0]
                    h_odds = b["markets"][0]["outcomes"][0]["price"]
                    a_odds = b["markets"][0]["outcomes"][1]["price"]
                    matches.append({
                        "home": home,
                        "away": away,
                        "odds": {"home": h_odds,"away": a_odds},
                        "commence_time": commence
                    })
            if matches:
                break
        except Exception as e:
            print(f"❌ Wyjątek przy pobieraniu meczów ({league}): {e}")
            continue
    print(f"ℹ️ Znaleziono {len(matches)} mecze w {league}")
    return matches

# ================= GENEROWANIE TYPU =================
def generate_pick(match):
    home = match["home"]
    away = match["away"]
    h_odds = match["odds"]["home"]
    a_odds = match["odds"]["away"]

    prob_home = random.uniform(0.4,0.6)
    prob_away = 1 - prob_home

    val_home = prob_home - 1/h_odds
    val_away = prob_away - 1/a_odds

    if val_home > 0 and val_home >= val_away:
        return {"selection": home, "odds": h_odds, "date": match["commence_time"], "home": home, "away": away}
    elif val_away > 0:
        return {"selection": away, "odds": a_odds, "date": match["commence_time"], "home": home, "away": away}
    return None

# ================= GENERUJ OFERTY (TESTOWA WERSJA) =================
def simulate_offers_test():
    coupons = load_coupons()
    now = datetime.now(timezone.utc)

    for league in LEAGUES:
        matches = get_upcoming_matches(league)
        if not matches:
            print(f"⚠️ Brak meczów do przetworzenia w {league}")
            continue

        for match in matches:
            match_dt = parser.isoparse(match["commence_time"])
            if match_dt < now or match_dt > now + timedelta(hours=MAX_HOURS_AHEAD):
                print(f"⚠️ Mecz poza limitem czasu: {match['home']} vs {match['away']}")
                continue

            # Ignorujemy, czy me
