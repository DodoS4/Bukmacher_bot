import requests
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from dateutil import parser
from collections import defaultdict

# ================= CONFIG =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS")
API_KEYS = [k for k in [
    os.getenv("ODDS_KEY"),
    os.getenv("ODDS_KEY_2"),
    os.getenv("ODDS_KEY_3")
] if k]

COUPONS_FILE = "coupons.json"
START_BANKROLL = 100.0
MAX_HOURS_AHEAD = 168  # testowo 7 dni
VALUE_THRESHOLD = 0.0  # testowo 0, żeby pokazać wszystkie typy
MIN_ODDS = 1.5          # testowo niskie kursy

LEAGUES = [
    "basketball_nba",
    "icehockey_nhl",
    "soccer_epl"
]

LEAGUE_INFO = {
    "basketball_nba": {"name": "NBA", "flag": "🏀"},
    "icehockey_nhl": {"name": "NHL", "flag": "🏒"},
    "soccer_epl": {"name": "Premier League", "flag": "⚽"}
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
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

# ================= TELEGRAM =================
def send_msg(text, target="types"):
    chat_id = T_CHAT_RESULTS if target=="results" else T_CHAT
    if not T_TOKEN or not chat_id:
        print("Brak tokena lub chat_id")
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
    except Exception as e:
        print("Błąd wysyłki Telegram:", e)

# ================= FORMAT =================
def format_match_time(dt):
    return dt.strftime("%d.%m.%Y • %H:%M UTC")

def format_value_card(league_key, home, away, dt, pick, odds, edge, stake):
    info = LEAGUE_INFO.get(league_key, {"name": league_key, "flag": "🎯"})
    return (
        f"{info['flag']} <b>VALUE BET • {info['name']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"<b>{home} vs {away}</b>\n"
        f"🕒 {format_match_time(dt)}\n"
        f"🎯 Typ: <b>{pick}</b>\n"
        f"📈 Kurs: <b>{odds}</b>\n"
        f"💎 Edge: <b>{round(edge*100,2)}%</b>\n"
        f"💰 Stawka: <stake} PLN"
    )

def format_btts_card(league_key, home, away, dt, pick, odds, edge, stake):
    info = LEAGUE_INFO.get(league_key, {"name": league_key, "flag": "🎯"})
    return (
        f"{info['flag']} <b>BTTS/OVER • {info['name']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"<b>{home} vs {away}</b>\n"
        f"🕒 {format_match_time(dt)}\n"
        f"🎯 Typ: <b>{pick}</b>\n"
        f"📈 Kurs: <b>{odds}</b>\n"
        f"💎 Edge: <b>{round(edge*100,2)}%</b>\n"
        f"💰 Stawka: <stake} PLN"
    )

# ================= ODDS / GENERATE PICK =================
def no_vig_probs(odds):
    inv = {k: 1/v for k,v in odds.items() if v}
    s = sum(inv.values())
    return {k:v/s for k,v in inv.items()}

def generate_value_pick(home, away, odds):
    probs = no_vig_probs({"home": odds.get(home), "away": odds.get(away)})
    best = None
    for sel, prob in probs.items():
        o = odds.get(home if sel==home else away)
        edge = prob - (1/o if o else 0)
        if o and edge >= VALUE_THRESHOLD:
            if not best or edge > best["val"]:
                best = {"sel": sel, "odds": o, "val": edge}
    return best

def generate_btts_over_pick(odds_totals):
    # testowo: pierwszy total
    for k,v in odds_totals.items():
        if k.lower() in ["over 2.5","btts yes","yes","btts"]:
            return {"sel":k,"odds":v,"val":0.02}  # dummy edge
    return None

# ================= MAIN =================
def run_debug():
    coupons = load_json(COUPONS_FILE, [])
    now = datetime.now(timezone.utc)
    value_matches = []
    btts_matches = []

    for league in LEAGUES:
        for key in API_KEYS:
            try:
                r = requests.get(
                    f"https://api.the-odds-api.com/v4/sports/{league}/odds",
                    params={"apiKey": key, "markets": "h2h,totals", "regions": "eu"},
                    timeout=10
                )
                if r.status_code != 200:
                    print(f"{league} - błąd API: {r.status_code}")
                    continue
                data = r.json()
                print(f"{league} - pobrano {len(data)} meczów")

                for e in data:
                    dt = parser.isoparse(e["commence_time"])
                    if not (now <= dt <= now + timedelta(hours=MAX_HOURS_AHEAD)):
                        continue

                    # h2h
                    odds_h2h = {}
                    for bm in e["bookmakers"]:
                        for m in bm["markets"]:
                            if m["key"]=="h2h":
                                for o in m["outcomes"]:
                                    odds_h2h[o["name"]] = max(odds_h2h.get(o["name"],0), o["price"])

                    # totals
                    odds_totals = {}
                    for bm in e["bookmakers"]:
                        for m in bm["markets"]:
                            if m["key"]=="totals":
                                for o in m["outcomes"]:
                                    odds_totals[o["name"]] = max(odds_totals.get(o["name"],0), o["price"])

                    # VALUE PICK
                    value_pick = generate_value_pick(e["home_team"], e["away_team"], odds_h2h)
                    if value_pick:
                        value_matches.append({
                            "league": league,
                            "home": e["home_team"],
                            "away": e["away_team"],
                            "pick": value_pick["sel"],
                            "odds": value_pick["odds"],
                            "edge": value_pick["val"],
                            "dt": dt
                        })

                    # BTTS/OVER PICK
                    btts_pick = generate_btts_over_pick(odds_totals)
                    if btts_pick:
                        btts_matches.append({
                            "league": league,
                            "home": e["home_team"],
                            "away": e["away_team"],
                            "pick": btts_pick["sel"],
                            "odds": btts_pick["odds"],
                            "edge": btts_pick["val"],
                            "dt": dt
                        })
                break
            except Exception as ex:
                print("Błąd:", ex)
                continue

    # --- Wyślij Value ---
    for m in value_matches:
        msg = format_value_card(m["league"], m["home"], m["away"], m["dt"], m["pick"], m["odds"], m["edge"], 3.0)
        send_msg(msg)

    # --- Wyślij BTTS/OVER ---
    for m in btts_matches:
        msg = format_btts_card(m["league"], m["home"], m["away"], m["dt"], m["pick"], m["odds"], m["edge"], 3.0)
        send_msg(msg)

    # --- Zapisz do pliku ---
    save_json(COUPONS_FILE, value_matches + btts_matches)

if __name__=="__main__":
    run_debug()