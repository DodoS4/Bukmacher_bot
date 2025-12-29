import requests
import os
import time
import json
from datetime import datetime, timedelta, timezone

# ================= KONFIGURACJA (TESTOWA) =================

T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")

KEYS_POOL = [
    os.getenv("ODDS_KEY"),
    os.getenv("ODDS_KEY_2"),
    os.getenv("ODDS_KEY_3"),
    os.getenv("ODDS_KEY_4"),
]
API_KEYS = [k for k in KEYS_POOL if k]

SPORTS_CONFIG = {
    "soccer_epl": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 PREMIER LEAGUE",
    "soccer_spain_la_liga": "🇪🇸 LA LIGA",
    "soccer_germany_bundesliga": "🇩🇪 BUNDESLIGA",
    "soccer_italy_serie_a": "🇮🇹 SERIE A",
    "soccer_poland_ekstraklasa": "🇵🇱 EKSTRAKLASA",
    "basketball_nba": "🏀 NBA",
    "icehockey_nhl": "🏒 NHL",
}

STATE_FILE = "sent.json"
MAX_DAYS = 7                 # Zwiększone do tygodnia
EV_THRESHOLD = 0.0           # PRZYJMIJ WSZYSTKO (Dla testu)
MIN_BOOKS = 1                # WYSTARCZY 1 BUKMACHER (Dla testu)
MIN_ODD = 1.10               # KAŻDY KURS (Dla testu)
MAX_ODD = 10.0
MAX_HOURS_AHEAD = 168        # SZUKAJ W CAŁYM TYGODNIU (Dla testu)

BANKROLL = 1000
KELLY_FRACTION = 0.1
TAX_RATE = 0.88

# ================= POMOCNICZE =================

def load_state():
    if not os.path.exists(STATE_FILE): 
        return {}
    try:
        with open(STATE_FILE, "r") as f: 
            return json.load(f)
    except:
        return {}

def save_state(state):
    with open(STATE_FILE, "w") as f: 
        json.dump(state, f)

def clean_state(state):
    now = datetime.now(timezone.utc)
    new_state = {}
    for key, ts in state.items():
        try:
            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            if now - dt <= timedelta(days=MAX_DAYS): 
                new_state[key] = ts
        except: 
            continue
    return new_state

def calculate_kelly_stake(odd, fair_odd):
    real_odd_netto = odd * TAX_RATE
    if real_odd_netto <= 1.0: return 2.0 # Minimalna stawka dla testu
    p = 1 / fair_odd
    b = real_odd_netto - 1
    kelly_percent = (b * p - (1 - p)) / b
    stake = BANKROLL * kelly_percent * KELLY_FRACTION
    return max(2.0, round(stake, 2))

def fair_odds(avg_h, avg_a):
    p_h, p_a = 1 / avg_h, 1 / avg_a
    total = p_h + p_a
    return 1 / (p_h / total), 1 / (p_a / total)

# ================= KOMUNIKACJA =================

def send_msg(text):
    print(f"Log: Próba wysyłki: {text[:50]}...")
    if not T_TOKEN or not T_CHAT: 
        print("Błąd: Brak T_TOKEN lub T_CHAT!")
        return
    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={"chat_id": T_CHAT, "text": text, "parse_mode": "Markdown"}, timeout=10)
        if r.status_code != 200:
            print(f"Błąd Telegrama: {r.status_code} - {r.text}")
    except Exception as e: 
        print(f"Błąd sieciowy: {e}")

# ================= GŁÓWNA PĘTLA =================

def run():
    print("🚀 Start bota testowego...")
    send_msg("🤖 *BOT TESTOWY URUCHOMIONY*\nFiltry wyłączone - szukam czegokolwiek...")
    
    if not API_KEYS: 
        print("❌ Brak kluczy API (ODDS_KEY)!")
        return
    
    state = clean_state(load_state())
    now = datetime.now(timezone.utc)

    for sport_key, sport_label in SPORTS_CONFIG.items():
        print(f"Skanuję: {sport_label}...")
        matches = None
        for key in API_KEYS:
            try:
                r = requests.get(f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/",
                                params={"apiKey": key, "regions": "eu", "markets": "h2h"}, timeout=10)
                if r.status_code == 200:
                    matches = r.json()
                    break
            except: continue

        if not matches: 
            print(f"Brak meczów dla {sport_key}")
            continue

        for match in matches:
            try:
                m_id = match["id"]
                home = match["home_team"]
                away = match["away_team"]
                m_dt = datetime.fromisoformat(match["commence_time"].replace('Z', '+00:00'))

                # Poluzowany filtr czasu
                if m_dt < now or m_dt > (now + timedelta(hours=MAX_HOURS_AHEAD)):
                    continue

                odds_h, odds_a = [], []
                for bm in match.get("bookmakers", []):
                    for market in bm.get("markets", []):
                        if market["key"] == "h2h":
                            h_val = next(o["price"] for o in market["outcomes"] if o["name"] == home)
                            a_val = next(o["price"] for o in market["outcomes"] if o["name"] == away)
                            odds_h.append(h_val)
                            odds_a.append(a_val)

                if len(odds_h) < MIN_BOOKS: continue

                avg_h = sum(odds_h) / len(odds_h)
                avg_a = sum(odds_a) / len(odds_a)
                fair_h, fair_a = fair_odds(avg_h, avg_a)

                max_h, max_a = max(odds_h), max(odds_a)
                ev_h_net = (max_h * TAX_RATE / fair_h - 1) * 100
                ev_a_net = (max_a * TAX_RATE / fair_a - 1) * 100

                if ev_h_net > ev_a_net:
                    pick, odd, fair, ev_n = home, max_h, fair_h, ev_h_net
                else:
                    pick, odd, fair, ev_n = away, max_a, fair_a, ev_a_net

                # TEST: Ignorujemy ev_n >= EV_THRESHOLD, żeby wysłać cokolwiek
                if odd >= MIN_ODD and f"{m_id}_test" not in state:
                    msg = (
                        f"🧪 *TESTOWY MECZ*\n"
