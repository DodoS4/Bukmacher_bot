import requests
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from dateutil import parser

# ================= CONFIG =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")             # Typy
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS")  # Wyniki/rozliczenia

API_KEYS = [k for k in [
    os.getenv("ODDS_KEY"),
    os.getenv("ODDS_KEY_2"),
    os.getenv("ODDS_KEY_3")
] if k]

COUPONS_FILE = "coupons.json"
BANKROLL_FILE = "bankroll.json"
START_BANKROLL = 100.0

MAX_HOURS_AHEAD = 48
VALUE_THRESHOLD = 0.035
KELLY_FRACTION = 0.25

# ================= LIGI =================
LEAGUES = [
    "basketball_nba",
    "soccer_epl",
    "icehockey_nhl",
    "soccer_poland_ekstraklasa",
    "soccer_uefa_champs_league",
    "soccer_germany_bundesliga",
    "soccer_italy_serie_a",
    "basketball_euroleague"
]

LEAGUE_INFO = {
    "basketball_nba": {"name": "NBA", "flag": "🏀"},
    "soccer_epl": {"name": "Premier League", "flag": "⚽ PL"},
    "icehockey_nhl": {"name": "NHL", "flag": "🏒"},
    "soccer_poland_ekstraklasa": {"name": "Ekstraklasa", "flag": "⚽ EK"},
    "soccer_uefa_champs_league": {"name": "Champions League", "flag": "🏆 CL"},
    "soccer_germany_bundesliga": {"name": "Bundesliga", "flag": "🇩🇪"},
    "soccer_italy_serie_a": {"name": "Serie A", "flag": "🇮🇹"},
    "basketball_euroleague": {"name": "EuroLeague", "flag": "🏀"}
}

MIN_ODDS = {
    "basketball_nba": 1.8,
    "icehockey_nhl": 2.3,
    "soccer_epl": 2.5,
    "soccer_poland_ekstraklasa": 2.5,
    "soccer_uefa_champs_league": 2.5,
    "soccer_germany_bundesliga": 2.5,
    "soccer_italy_serie_a": 2.5,
    "basketball_euroleague": 1.8
}

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
    # Konwertuj datetime na string, jeśli jest w strukturze
    def convert(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, default=convert)

# ================= BANKROLL =================
def load_bankroll():
    return load_json(BANKROLL_FILE, {}).get("bankroll", START_BANKROLL)

def save_bankroll(val):
    save_json(BANKROLL_FILE, {"bankroll": round(val, 2)})

def calc_kelly_stake(bankroll, odds, edge):
    if edge <= 0 or odds <= 1:
        return 0.0
    b = odds - 1
    kelly = edge / b
    stake = bankroll * kelly * KELLY_FRACTION
    stake = max(3.0, stake)
    stake = min(stake, bankroll * 0.05)
    return round(stake, 2)

# ================= TELEGRAM =================
def send_msg(text, target="types"):
    chat_id = T_CHAT_RESULTS if target=="results" else T_CHAT
    print(f"DEBUG: Sending message to chat_id={chat_id}")  # Debug log
    if not T_TOKEN or not chat_id:
        print("DEBUG: T_TOKEN lub chat_id nie ustawione!")
        return
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            },
            timeout=10
        )
        print(f"DEBUG: Telegram response {r.status_code} | {r.text}")
    except Exception as e:
        print(f"DEBUG: Exception sending message: {e}")

# ================= FORMAT UI =================
def format_match_time(dt):
    return dt.strftime("%d.%m.%Y • %H:%M UTC")

def format_value_card(match):
    return (
        f"{LEAGUE_INFO.get(match['league'],{'flag':'🎯','name':match['league']})['flag']} "
        f"<b>VALUE BET • {LEAGUE_INFO.get(match['league'],{'name':match['league']})['name']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"<b>{match['home']} vs {match['away']}</b>\n"
        f"🕒 {format_match_time(parser.isoparse(match['dt']))}\n"
        f"🎯 Typ: <b>{match['picked']}</b>\n"
        f"📈 Kurs: <b>{match['odds']}</b>\n"
        f"💎 Edge: <b>{round(match['val']*100,2)}%</b>\n"
        f"💰 Stawka: <b>{match['stake']} PLN</b>"
    )

def format_btts_over_card(match):
    return (
        f"{LEAGUE_INFO.get(match['league'],{'flag':'🎯','name':match['league']})['flag']} "
        f"<b>{match['type'].upper()} • {LEAGUE_INFO.get(match['league'],{'name':match['league']})['name']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"<b>{match['home']} vs {match['away']}</b>\n"
        f"🕒 {format_match_time(parser.isoparse(match['dt']))}\n"
        f"🎯 Typ: <b>{match['picked']}</b>\n"
        f"📈 Kurs: <b>{match['odds']}</b>\n"
        f"💎 Edge: <b>{round(match['val']*100,2)}%</b>\n"
        f"💰 Stawka: <b>{match['stake']} PLN</b>"
    )

# ================= ODDS / PICK =================
def no_vig_probs(odds):
    inv = {k: 1/v for k,v in odds.items() if v}
    s = sum(inv.values())
    return {k: v/s for k,v in inv.items()}

def generate_pick(match):
    h_o = match["odds"]["home"]
    a_o = match["odds"]["away"]
    d_o = match["odds"].get("draw")
    if match.get("type")=="value":
        if match["league"]=="icehockey_nhl":
            probs = no_vig_probs({"home": h_o, "away": a_o})
            p = {match["home"]: probs["home"], match["away"]: probs["away"]}
        else:
            probs = no_vig_probs({"home": h_o, "away": a_o, "draw": d_o})
            p = {match["home"]: probs["home"], match["away"]: probs["away"], "Remis": probs.get("draw",0)*0.9}
    else:
        # BTTS/Over zakładamy edge mniejsze
        p = {match["picked"]: 0.52}  # przykładowa symulacja

    min_odds = MIN_ODDS.get(match["league"], 2.5)
    best = None
    for sel, prob in p.items():
        odds = h_o if sel==match["home"] else a_o if sel==match["away"] else d_o
        if odds and odds >= min_odds:
            edge = prob - (1/odds)
            if edge >= VALUE_THRESHOLD:
                if not best or edge > best["val"]:
                    best = {"sel": sel, "odds": odds, "val": edge}
    return best

# ================= RUN =================
def run():
    coupons = load_json(COUPONS_FILE, [])
    bankroll = load_bankroll()
    now = datetime.now(timezone.utc)

    value_matches = []
    btts_over_matches = []

    # --- tutaj symulacja pobrania typów z API ---
    # dla testu dodajemy 2 przykładowe typy
    test_value = {
        "home": "Team A", "away": "Team B", "league":"basketball_nba",
        "picked":"Team A","odds":2.5,"val":0.08,"stake":10,"dt":str(now),"type":"value"
    }
    test_btts = {
        "home": "Team C","away":"Team D","league":"basketball_nba",
        "picked":"Over 2.5","odds":1.8,"val":0.02,"stake":5,"dt":str(now),"type":"btts_over"
    }

    value_matches.append(test_value)
    btts_over_matches.append(test_btts)

    # --- wysyłka VALUE ---
    for m in value_matches:
        send_msg(format_value_card(m), target="types")

    # --- wysyłka BTTS/OVER ---
    for m in btts_over_matches:
        send_msg(format_btts_over_card(m), target="types")

    # --- zapis do pliku ---
    save_json(COUPONS_FILE, value_matches+btts_over_matches)
    save_bankroll(bankroll)

# ================= MAIN =================
if __name__=="__main__":
    if "--stats" in sys.argv:
        print("DEBUG: stats mode")
        # tutaj możesz wczytać plik coupons i wysłać statystyki
    else:
        run()