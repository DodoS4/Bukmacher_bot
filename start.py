import requests
import os
import time
from datetime import datetime, timedelta, timezone

# --- KONFIGURACJA ---
T_TOKEN = os.getenv('T_TOKEN')
T_CHAT = os.getenv('T_CHAT')

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


# --- FUNKCJE ---
def send_msg(txt):
    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
    payload = {'chat_id': T_CHAT, 'text': txt, 'parse_mode': 'Markdown'}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print("Telegram error:", e)


def is_already_sent(match_id, category=""):
    key = f"{match_id}_{category}"
    if not os.path.exists(DB_FILE):
        open(DB_FILE, 'w').close()
        return False
    with open(DB_FILE, "r") as f:
        return key in f.read().splitlines()


def mark_as_sent(match_id, category=""):
    with open(DB_FILE, "a") as f:
        f.write(f"{match_id}_{category}\n")


def fetch_odds(sport_key):
    for i, key in enumerate(API_KEYS):
        url = (
            f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/"
            f"?apiKey={key}&regions=eu&markets=h2h"
        )
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                return r.json()
            elif r.status_code == 429:
                print(f"⚠️ Klucz {i+1} limit – przełączam")
        except Exception as e:
            print("API error:", e)
    return None


def calculate_ev(avg_odds, best_odds):
    return (best_odds * (1 / avg_odds))_*_
