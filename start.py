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
MAX_HOURS_AHEAD = 168  # 7 dni dla testów

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
    for a
