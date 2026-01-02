import requests
import os
import json
from datetime import datetime, timedelta, timezone

# ================= KONFIGURACJA =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")
KEYS_POOL = [os.getenv(f"ODDS_KEY{i}") for i in ["", "_2", "_3", "_4", "_5"]]
API_KEYS = [k for k in KEYS_POOL if k]

# PROGI KURSOWE (Zoptymalizowane pod polski rynek i podatek)
MIN_SINGLE_ODD = 1.35
MAX_SINGLE_ODD = 1.95
SINGLE_THRESHOLD = 2.05  
TAX_RATE = 0.88

STAKE_STANDARD = 50.0    
STAKE_SINGLE = 80.0      

# FILTRY (Ustawienia startowe dla dobrej widoczności ofert)
MAX_VARIANCE = 0.12
MIN_BOOKMAKERS = 4

SPORTS_CONFIG = {
    "soccer_epl": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League", 
    "soccer_spain_la_liga": "🇪🇸 La Liga",
    "soccer_germany_bundesliga": "🇩🇪 Bundesliga", 
    "soccer_italy_serie_a": "🇮🇹 Serie A",
    "soccer_france_ligue_one": "🇫🇷 Ligue 1", 
    "soccer_poland_ekstraklasa": "🇵🇱 Ekstraklasa",
    "soccer_netherlands_ere_divisie": "🇳🇱 Eredivisie",
    "soccer_portugal_primeira_liga": "🇵🇹 Primeira Liga",
    "soccer_uefa_champions_league": "🇪🇺 Liga Mistrzów", 
    "soccer_uefa_europa_league": "🇪🇺 Liga Europy",
    "basketball_nba": "🏀 NBA"
}

# Nazwa pliku bazy danych w Twoim repozytorium
COUPONS_FILE = "coupons.json"

# ================= FUNKCJE POMOCNICZE =================

def load_coupons():
    if not os.path.exists(COUPONS_FILE): return []
    try:
        with open(COUPONS_FILE, "r") as f: return json.load(f)
    except: return []

def save_coupons(coupons):
    with open(COUPONS_FILE, "w") as f: 
        json.dump(coupons[-500:], f, indent=4)

def send_msg(text):
    if not T_TOKEN or not T_CHAT: return
    url = f"https://
