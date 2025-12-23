import requests
import os
import time
from datetime import datetime, timedelta, timezone

# --- KONFIGURACJA ---
T_TOKEN = os.getenv('T_TOKEN')
T_CHAT = os.getenv('T_CHAT')

# LISTA KLUCZY API
KEYS_POOL = [
    os.getenv('ODDS_KEY'),
    os.getenv('ODDS_KEY_2'),
    os.getenv('ODDS_KEY_3'),
    os.getenv('ODDS_KEY_4')
]
API_KEYS = [k for k in KEYS_POOL if k]

SPORTS_CONFIG = {
    'soccer_epl': '⚽ PREMIER LEAGUE',
    'soccer_spain_la_liga': '⚽ LA LIGA',
    'soccer_germany_bundesliga': '⚽ BUNDESLIGA',
    'soccer_italy_serie_a': '⚽ SERIE A',
    'soccer_poland_ekstraklasa': '⚽ EKSTRAKLASA',
    'basketball_nba': '🏀 NBA',
    'icehockey_nhl': '🏒 NHL',
    'mma_mixed_martial_arts': '🥊 MMA/UFC'
}

DB_FILE = "sent_matches.txt"

# ----------------- FUNKCJE -----------------

def send_msg(txt):
    if not T_TOKEN or not T_CHAT:
        print("❌ Brak tokena lub chat ID Telegrama!")
        return
    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
    payload = {'chat_id': T_CHAT, 'text': txt, 'parse_mode': 'Markdown'}
    try:
        requests.post(url, json=payload, timeout=10)
    except requests.exceptions.RequestException as e:
        print(f"⚠️ Błąd wysyłki Telegram: {e}")

def is_already_sent(match_id, category=""):
    unique_key = f"{match_id}_{category}"
    if not os.path.exists(DB_FILE):
        open(DB_FILE, 'w').close()
        return False
    with open(DB_FILE, "r") as f:
        return unique_key in f.read().splitlines()

def mark_as_sent(match_id, category=""):
    with open(DB_FILE, "a") as f:
        f.write(f"{match_id}_{category}\n")

def fetch_odds(sport_key):
    """Próbuje pobrać dane używając dostępnych kluczy po kolei."""
    for i, key in enumerate(API_KEYS):
        url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/"
        params = {'apiKey': key, 'regions': 'eu', 'markets': 'h2h'}
        try:
            response = requests.get(url, params=params, timeout=10
