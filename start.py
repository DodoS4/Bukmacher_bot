import requests
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from dateutil import parser

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
BANKROLL_FILE = "bankroll.json"
START_BANKROLL = 100.0

MAX_HOURS_AHEAD = 168  # Sprawdzanie meczy w ciągu tygodnia
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
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, default=str)  # default=str do daty

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

# ================= FORMAT UI =================
def format_match_time(dt):
    return dt.strftime("%d.%m.%Y • %H:%M UTC")

def format_value_card(match):
    info = LEAGUE_INFO.get(match["league"], {"name": match["league"], "flag": "🎯"})
    tier = "A" if match["edge"] >= 0.08 else "B"
    return (
        f"{info['flag']} <b>VALUE BET • {info['name']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"<b>{match['home']} vs {match['away']}</b>\n"
        f"🕒 {format_match_time(match['dt'])}\n"
        f"🎯 Typ: <b>{match['pick']}</b>\n"
        f"📈 Kurs: <b>{match['odds']}</b>\n"
        f"💎 Edge: <b>+{round(match['edge']*100,2)}%</b>\n"
        f"🏷 Tier: <b>{tier}</b>\n"
        f"💰 Stawka: <b>{match['stake']} PLN</b>"
    )

def format_btts_card(match):
    info = LEAGUE_INFO.get(match["league"], {"name": match["league"], "flag": "🎯"})
    return (
        f"{info['flag']} <b>{match['pick']} • {info['name']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"<b>{match['home']} vs {match['away']}</b>\n"
        f"🕒 {format_match_time(match['dt'])}\n"
        f"🎯 Typ: <b>{match['pick']}</b>\n"
        f"📈 Kurs: <b>{match['odds']}</b>\n"
        f"💰 Stawka: <b>{match['stake']} PLN</b>"
    )

# ================= ODDS LOGIC =================
def no_vig_probs(odds):
    inv = {k: 1/v for k, v in odds.items() if v}
    s = sum(inv.values())
    return {k: v/s for k, v in inv.items()}

def generate_value_pick(match):
    h_o = match["odds"]["home"]
    a_o = match["odds"]["away"]
    d_o = match["odds"].get("draw")

    if match["league"] == "icehockey_nhl":
        probs = no_vig_probs({"home": h_o, "away": a_o})
        p = {match["home"]: probs["home"], match["away"]: probs["away"]}
    else:
        probs = no_vig_probs({"home": h_o, "away": a_o, "draw": d_o})
        p = {match["home"]: probs["home"], match["away"]: probs["away"], "Remis": probs.get("draw",0)*0.9}

    min_odds = MIN_ODDS.get(match["league"], 2.5)
    best = None
    for sel, prob in p.items():
        odds = h_o if sel==match["home"] else a_o if sel==match["away"] else d_o
        if odds and odds >= min_odds:
            edge = prob - (1/odds)
            if edge >= VALUE_THRESHOLD:
                if not best or edge > best["val"]:
                    best = {"sel": sel, "odds": odds, "val": edge}
    if best:
        return {"pick": best["sel"], "odds": best["odds"], "edge": best["val"]}
    return None

def generate_btts_over_pick(match):
    # uproszczona logika: jeśli kurs > MIN_ODDS, to wysyłamy typ
    # możesz dodać bardziej zaawansowaną logikę później
    min_odds = 1.8
    for pick_type in ["BTTS","Over 2.5"]:
        odds = match["odds"].get(pick_type)
        if odds and odds >= min_odds:
            return {"pick": pick_type, "odds": odds, "edge": 0.02}  # edge testowy
    return None

# ================= RUN =================
def run():
    coupons = load_json(COUPONS_FILE, [])
    bankroll = load_bankroll()
    now = datetime.now(timezone.utc)

    value_matches = []
    btts_matches = []

    for league in LEAGUES:
        for key in API_KEYS:
            try:
                r = requests.get(f"https://api.the-odds-api.com/v4/sports/{league}/odds",
                                 params={"apiKey": key,"markets":"h2h,totals,btts","regions":"eu"},
                                 timeout=10)
                if r.status_code != 200: continue

                for e in r.json():
                    dt = parser.isoparse(e["commence_time"])
                    if not(now <= dt <= now + timedelta(hours=MAX_HOURS_AHEAD)):
                        continue

                    # Budowanie kursów
                    odds = {}
                    for bm in e["bookmakers"]:
                        for m in bm["markets"]:
                            if m["key"]=="h2h":
                                for o in m["outcomes"]:
                                    odds[o["name"]] = max(odds.get(o["name"],0), o["price"])
                            elif m["key"]=="totals" or m["key"]=="btts":
                                for o in m["outcomes"]:
                                    odds[o["name"]] = max(odds.get(o["name"],0), o["price"])

                    match_info = {
                        "home": e["home_team"],
                        "away": e["away_team"],
                        "league": league,
                        "odds": odds,
                        "dt": dt
                    }

                    # VALUE
                    val = generate_value_pick(match_info)
                    if val:
                        stake = calc_kelly_stake(bankroll, val["odds"], val["edge"])
                        bankroll -= stake
                        match_val = {**match_info, **val, "stake": stake}
                        value_matches.append(match_val)
                        coupons.append({**match_val, "type":"value","status":"pending","win_val":0,"sent_date":str(now.date())})

                    # BTTS / Over
                    btts = generate_btts_over_pick(match_info)
                    if btts:
                        stake = max(3.0, bankroll*0.01)
                        bankroll -= stake
                        match_btts = {**match_info, **btts, "stake": stake}
                        btts_matches.append(match_btts)
                        coupons.append({**match_btts, "type":"btts_over","status":"pending","win_val":0,"sent_date":str(now.date())})

                break
            except: continue

    # Wysyłanie wiadomości
    for match in value_matches:
        send_msg(format_value_card(match))
    for match in btts_matches:
        send_msg(format_btts_card(match))

    save_bankroll(bankroll)
    save_json(COUPONS_FILE, coupons)

# ================= MAIN =================
if __name__=="__main__":
    run()