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
    def default(o):
        if isinstance(o, datetime):
            return o.isoformat()
        return o
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, default=default)

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
    if not T_TOKEN or not chat_id:
        print("❌ Brak tokena lub chat_id!")
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
        print(f"❌ Błąd wysyłki telegram: {e}")

# ================= FORMAT =================
def format_match_time(dt):
    if isinstance(dt, str):
        dt = parser.isoparse(dt)
    return dt.strftime("%d.%m.%Y • %H:%M UTC")

def format_value_card(c):
    info = LEAGUE_INFO.get(c['league'], {"name": c['league'], "flag":"🎯"})
    return (
        f"{info['flag']} VALUE BET • {info['name']}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{c['home']} vs {c['away']}\n"
        f"🕒 {format_match_time(c['dt'])}\n"
        f"🎯 Typ: {c['picked']}\n"
        f"📈 Kurs: {c['odds']}\n"
        f"💎 Edge: {round(c.get('val',0)*100,2)}%\n"
        f"💰 Stawka: {c['stake']} PLN"
    )

def format_btts_card(c):
    info = LEAGUE_INFO.get(c['league'], {"name": c['league'], "flag":"🎯"})
    return (
        f"{info['flag']} BTTS_OVER • {info['name']}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{c['home']} vs {c['away']}\n"
        f"🕒 {format_match_time(c['dt'])}\n"
        f"🎯 Typ: {c['picked']}\n"
        f"📈 Kurs: {c['odds']}\n"
        f"💎 Edge: {round(c.get('val',0)*100,2)}%\n"
        f"💰 Stawka: {c['stake']} PLN"
    )

# ================= ODDS / VALUE =================
def no_vig_probs(odds):
    inv = {k: 1/v for k,v in odds.items() if v}
    s = sum(inv.values())
    return {k: v/s for k,v in inv.items()}

def generate_pick(match, bet_type="value"):
    h_o = match["odds"].get("home")
    a_o = match["odds"].get("away")
    d_o = match["odds"].get("draw")

    if match["league"]=="icehockey_nhl":
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
            if bet_type=="value" and edge >= VALUE_THRESHOLD:
                if not best or edge>best["val"]:
                    best = {"sel": sel, "odds": odds, "val": edge}
            elif bet_type=="btts_over":
                if not best or edge>best.get("val",0):
                    best = {"sel": sel, "odds": odds, "val": edge}
    return best

# ================= RUN =================
def run():
    coupons = load_json(COUPONS_FILE, [])
    bankroll = load_bankroll()
    now = datetime.now(timezone.utc)
    all_picks_value = []
    all_picks_btts = []

    for league in LEAGUES:
        for key in API_KEYS:
            try:
                r = requests.get(
                    f"https://api.the-odds-api.com/v4/sports/{league}/odds",
                    params={"apiKey": key, "markets": "h2h", "regions": "eu"},
                    timeout=10
                )
                if r.status_code!=200: continue
                data = r.json()
                for e in data:
                    dt = parser.isoparse(e["commence_time"])
                    if not(now<=dt<=now+timedelta(hours=MAX_HOURS_AHEAD)): continue

                    odds={}
                    for bm in e.get("bookmakers",[]):
                        for m in bm.get("markets",[]):
                            if m["key"]=="h2h":
                                for o in m.get("outcomes",[]):
                                    odds[o["name"]] = max(odds.get(o["name"],0), o["price"])

                    # VALUE
                    pick_value = generate_pick({
                        "home": e["home_team"],
                        "away": e["away_team"],
                        "league": league,
                        "odds": {"home": odds.get(e["home_team"]), "away": odds.get(e["away_team"]), "draw": odds.get("Draw")}
                    }, bet_type="value")

                    if pick_value and not any(c for c in coupons if c["home"]==e["home_team"] and c["away"]==e["away_team"] and c["sent_date"]==str(now.date()) and c["type"]=="value"):
                        stake = calc_kelly_stake(bankroll, pick_value["odds"], pick_value["val"])
                        bankroll -= stake
                        save_bankroll(bankroll)
                        coupons.append({
                            "home": e["home_team"],
                            "away": e["away_team"],
                            "picked": pick_value["sel"],
                            "odds": pick_value["odds"],
                            "stake": stake,
                            "league": league,
                            "status": "pending",
                            "win_val": 0,
                            "sent_date": str(now.date()),
                            "dt": dt,
                            "val": pick_value["val"],
                            "type": "value"
                        })
                        all_picks_value.append(coupons[-1])

                    # BTTS/Over (przykładowo typ dynamiczny)
                    pick_btts = generate_pick({
                        "home": e["home_team"],
                        "away": e["away_team"],
                        "league": league,
                        "odds": {"home": odds.get(e["home_team"]), "away": odds.get(e["away_team"]), "draw": odds.get("Draw")}
                    }, bet_type="btts_over")

                    if pick_btts and not any(c for c in coupons if c["home"]==e["home_team"] and c["away"]==e["away_team"] and c["sent_date"]==str(now.date()) and c["type"]=="btts_over"):
                        stake = calc_kelly_stake(bankroll, pick_btts["odds"], pick_btts["val"])
                        bankroll -= stake
                        save_bankroll(bankroll)
                        coupons.append({
                            "home": e["home_team"],
                            "away": e["away_team"],
                            "picked": pick_btts["sel"],
                            "odds": pick_btts["odds"],
                            "stake": stake,
                            "league": league,
                            "status": "pending",
                            "win_val": 0,
                            "sent_date": str(now.date()),
                            "dt": dt,
                            "val": pick_btts["val"],
                            "type": "btts_over"
                        })
                        all_picks_btts.append(coupons[-1])
                break
            except: continue

    # Wyślij osobne wiadomości
    for c in all_picks_value:
        send_msg(format_value_card(c), target="types")
    for c in all_picks_btts:
        send_msg(format_btts_card(c), target="types")

    save_json(COUPONS_FILE, coupons)

# ================= MAIN =================
if __name__=="__main__":
    run()