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

MAX_HOURS_AHEAD = 48  # 48 godzin do przodu
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
        json.dump(data, f, indent=4, default=str)  # default=str dla datetime

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
    if isinstance(dt, str):
        dt = parser.isoparse(dt)
    return dt.strftime("%d.%m.%Y • %H:%M UTC")

def format_value_card(match):
    info = LEAGUE_INFO.get(match["league"], {"name": match["league"], "flag": "🎯"})
    tier = "A" if match.get("edge",0)>=0.08 else "B"
    return (
        f"{info['flag']} <b>{match['type'].upper()} • {info['name']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"<b>{match['home']} vs {match['away']}</b>\n"
        f"🕒 {format_match_time(match['dt'])}\n"
        f"🎯 Typ: <b>{match['picked']}</b>\n"
        f"📈 Kurs: <b>{match['odds']}</b>\n"
        f"💎 Edge: <b>{round(match.get('edge',0)*100,2)}%</b>\n"
        f"🏷 Tier: <b>{tier}</b>\n"
        f"💰 Stawka: <b>{match['stake']} PLN</b>"
    )

# ================= ODDS =================
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
    return best

# ================= RUN =================
def run():
    coupons = load_json(COUPONS_FILE, [])
    bankroll = load_bankroll()
    now = datetime.now(timezone.utc)

    value_matches = []
    btts_over_matches = []

    for league in LEAGUES:
        for key in API_KEYS:
            try:
                r = requests.get(f"https://api.the-odds-api.com/v4/sports/{league}/odds",
                                 params={"apiKey": key,"markets":"h2h,totals","regions":"eu"},
                                 timeout=10)
                if r.status_code != 200:
                    continue

                for e in r.json():
                    dt = parser.isoparse(e["commence_time"])
                    if not(now <= dt <= now + timedelta(hours=MAX_HOURS_AHEAD)):
                        continue

                    # h2h odds
                    odds_h2h = {}
                    for bm in e["bookmakers"]:
                        for m in bm["markets"]:
                            if m["key"]=="h2h":
                                for o in m["outcomes"]:
                                    odds_h2h[o["name"]] = max(odds_h2h.get(o["name"],0), o["price"])

                    # totals (BTTS / Over)
                    odds_totals = {}
                    for bm in e["bookmakers"]:
                        for m in bm["markets"]:
                            if m["key"]=="totals":
                                for o in m["outcomes"]:
                                    odds_totals[o["name"]] = max(odds_totals.get(o["name"],0), o["price"])

                    # --- Value Bets ---
                    value_pick = generate_value_pick({
                        "home":e["home_team"],
                        "away":e["away_team"],
                        "league":league,
                        "odds":{"home":odds_h2h.get(e["home_team"]),
                                "away":odds_h2h.get(e["away_team"]),
                                "draw":odds_h2h.get("Draw")}
                    })
                    if value_pick:
                        # unikaj duplikatów Value
                        if not any(c for c in coupons if c["home"]==e["home_team"] and c["away"]==e["away_team"] and c.get("type")=="value" and c["picked"]==value_pick["sel"]):
                            stake = calc_kelly_stake(bankroll,value_pick["odds"],value_pick["val"])
                            bankroll -= stake
                            save_bankroll(bankroll)
                            match_data = {
                                "home":e["home_team"],
                                "away":e["away_team"],
                                "picked":value_pick["sel"],
                                "odds":value_pick["odds"],
                                "edge":value_pick["val"],
                                "stake":stake,
                                "league":league,
                                "dt":str(dt),
                                "type":"value"
                            }
                            value_matches.append(match_data)
                            coupons.append(match_data)

                    # --- BTTS / Over ---
                    for total_name in ["Over 2.5","Yes","BTTS"]:
                        if total_name in odds_totals and odds_totals[total_name]>=1.7:
                            stake = round(bankroll*0.02,2)
                            match_data = {
                                "home":e["home_team"],
                                "away":e["away_team"],
                                "picked":total_name,
                                "odds":odds_totals[total_name],
                                "edge":0.02,
                                "stake":stake,
                                "league":league,
                                "dt":str(dt),
                                "type":"btts_over"
                            }
                            if not any(c for c in coupons if c["home"]==e["home_team"] and c["away"]==e["away_team"] and c.get("type")=="btts_over" and c["picked"]==total_name):
                                btts_over_matches.append(match_data)
                                coupons.append(match_data)

                break
            except:
                continue

    # --- Wyślij wiadomości ---
    for m in value_matches:
        send_msg(format_value_card(m))
    for m in btts_over_matches:
        send_msg(format_value_card(m))

    save_json(COUPONS_FILE, coupons)

# ================= MAIN =================
if __name__=="__main__":
    if "--stats" in sys.argv:
        from stats import main as send_stats
        send_stats()
    else:
        run()