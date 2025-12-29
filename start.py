import requests
import os
import json
from datetime import datetime, timedelta, timezone

# ================= KONFIGURACJA =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")
# Pula 5 kluczy API pobierana z GitHub Secrets
KEYS_POOL = [os.getenv(f"ODDS_KEY{i}") for i in ["", "_2", "_3", "_4", "_5"]]
API_KEYS = [k for k in KEYS_POOL if k]

# Ligi do skanowania
SPORTS_CONFIG = {
    "soccer_epl": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 PREMIER LEAGUE",
    "soccer_spain_la_liga": "🇪🇸 LA LIGA",
    "soccer_germany_bundesliga": "🇩🇪 BUNDESLIGA",
    "soccer_italy_serie_a": "🇮🇹 SERIE A",
    "soccer_france_ligue_one": "🇫🇷 LIGUE 1",
    "soccer_poland_ekstraklasa": "🇵🇱 EKSTRAKLASA",
    "basketball_nba": "🏀 NBA",
    "icehockey_nhl": "🏒 NHL",
}

STATE_FILE = "sent.json"
HISTORY_FILE = "history.json"

# PARAMETRY STRATEGII
BANKROLL = 1000              
EV_THRESHOLD = 3.5           # Próg opłacalności (%)
MIN_ODD = 1.40               
MAX_ODD = 4.50               
TAX_RATE = 0.88              # Polski podatek 12%
KELLY_FRACTION = 0.1         

# ================= CZAS POLSKI =================

def is_poland_dst():
    """Automatyczne wykrywanie czasu letniego/zimowego w Polsce."""
    now = datetime.now(timezone.utc)
    dst_start = datetime(now.year, 3, 31, 1, tzinfo=timezone.utc)
    dst_start -= timedelta(days=(dst_start.weekday() + 1) % 7)
    dst_end = datetime(now.year, 10, 31, 1, tzinfo=timezone.utc)
    dst_end -= timedelta(days=(dst_end.weekday() + 1) % 7)
    return dst_start <= now < dst_end

def get_poland_hour():
    offset = 2 if is_poland_dst() else 1
    return (datetime.now(timezone.utc) + timedelta(hours=offset)).hour

# ================= SYSTEM DANYCH =================

def load_data(file):
    if not os.path.exists(file): return {} if "sent" in file else []
    try:
        with open(file, "r") as f:
            data = json.load(f)
            return data if data else ([] if "history" in file else {})
    except: return {} if "sent" in file else []

def save_data(file, data):
    with open(file, "w") as f: json.dump(data, f)

def send_msg(text):
    if not T_TOKEN or not T_CHAT: return
    try:
        requests.post(f"https://api.telegram.org/bot{T_TOKEN}/sendMessage", 
                      json={"chat_id": T_CHAT, "text": text, "parse_mode": "Markdown"}, timeout=10)
    except Exception as e:
        print(f"Błąd Telegrama: {e}")

# ================= ROZLICZENIA =================

def fetch_score(sport_key, event_id):
    for key in API_KEYS:
        try:
            r = requests.get(f"https://api.the-odds-api.com/v4/sports/{sport_key}/scores/", 
                             params={"apiKey": key, "daysFrom": 3}, timeout=10)
            if r.status_code == 200:
                for s in r.json():
                    if s["id"] == event_id and s["completed"]:
                        h_score = int(next(item["score"] for item in s["scores"] if item["name"] == s["home_team"]))
                        a_score = int(next(item["score"] for item in s["scores"] if item["name"] == s["away_team"]))
                        return h_score, a_score
            elif r.status_code == 429: continue 
        except: continue
    return None

def check_results():
    history = load_data(HISTORY_FILE)
    if not history: return
    now = datetime.now(timezone.utc)
    updated_history = []
    for bet in history:
        m_dt = datetime.fromisoformat(bet["date"])
        if bet.get("status") == "pending" and now > (m_dt + timedelta(hours=4)):
            result = fetch_score(bet["sport"], bet["id"])
            if result:
                h_s, a_s = result
                is_win = (bet["pick"] == bet["home"] and h_s > a_s) or (bet["pick"] == bet["away"] and a_s > h_s)
                profit = round((bet["stake"] * bet["odd"] * TAX_RATE) - bet["stake"], 2) if is_win else -bet["stake"]
                send_msg(f"{'✅ WYGRANA' if is_win else '❌ PRZEGRANA'}\n\n🏟 {bet['home']} {h_s}:{a_s} {bet['away']}\n🎯 Typ: **{bet['pick'].upper()}**\n💰 Profit: `{profit} zł`")
                bet["status"] = "settled"
        if m_dt > (now - timedelta(days=7)): updated_history.append(bet)
    save_data(HISTORY_FILE, updated_history)

# ================= MATEMATYKA =================

def calculate_fair_odds(odds_h, odds_a, odds_d=None):
    """Oblicza sprawiedliwe kursy usuwając marżę bukmachera (obsługa 2-way i 3-way)."""
    avg_h = sum(odds_h)/len(odds_h)
    avg_a = sum(odds_a)/len(odds_a)
    if odds_d and len(odds_d) > 0:
        avg_d = sum(odds_d)/len(odds_d)
        p_total = (1/avg_h) + (1/avg_a) + (1/avg_d)
        return 1/((1/avg_h)/p_total), 1/((1/avg_a)/p_total)
    else:
        p_total = (1/avg_h) + (1/avg_a)
        return 1/((1/avg_h)/p_total), 1/((1/avg_a)/p_total)

def calculate_kelly_stake(odd, fair_odd):
    real_odd_netto = odd * TAX_RATE
    if real_odd_netto <= 1.0: return 0
    p = 1 / fair_odd
    b = real_odd_netto - 1
    kelly_percent = (b * p - (1 - p)) / b
    return max(0, round(BANKROLL * kelly_percent * KELLY_
