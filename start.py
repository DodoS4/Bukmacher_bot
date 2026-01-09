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
        json.dump(data, f, indent=4)

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
    dt_obj = parser.isoparse(dt) if isinstance(dt, str) else dt
    return dt_obj.strftime("%d.%m.%Y • %H:%M UTC")

def format_value_card(league_key, matches):
    msg = ""
    for m in matches:
        info = LEAGUE_INFO.get(league_key, {"name": league_key, "flag": "🎯"})
        msg += (
            f"{info['flag']} <b>VALUE BET • {info['name']}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"<b>{m['home']} vs {m['away']}</b>\n"
            f"🕒 {format_match_time(m['dt'])}\n"
            f"🎯 Typ: <b>{m['pick']}</b>\n"
            f"📈 Kurs: <b>{m['odds']}</b>\n"
            f"💎 Edge: <b>{round(m.get('edge',0)*100,2)}%</b>\n"
            f"💰 Stawka: <b>{m['stake']} PLN</b>\n\n"
        )
    return msg

def format_btts_card(matches):
    msg = "🏀/🏒 BTTS / OVER\n━━━━━━━━━━━━━━━━━━\n"
    for m in matches:
        info = LEAGUE_INFO.get(m["league"], {"flag":"🎯"})
        msg += (
            f"{info['flag']} {m['home']} vs {m['away']} | Typ: {m['pick']} | "
            f"Kurs: {m['odds']} | Stawka: {m['stake']} PLN | 🕒 {format_match_time(m['dt'])}\n"
        )
    return msg

# ================= ODDS =================
def no_vig_probs(odds):
    inv = {k: 1/v for k, v in odds.items() if v}
    s = sum(inv.values())
    return {k: v/s for k, v in inv.items()}

def generate_pick(match):
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
                    best = {"pick": sel, "odds": odds, "val": edge}
    return best

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
                r=requests.get(f"https://api.the-odds-api.com/v4/sports/{league}/odds",
                               params={"apiKey":key,"markets":"h2h,totals,btts","regions":"eu"},
                               timeout=10)
                if r.status_code!=200: continue

                for e in r.json():
                    dt=parser.isoparse(e["commence_time"])
                    if not(now<=dt<=now+timedelta(hours=MAX_HOURS_AHEAD)): continue

                    odds={}
                    for bm in e["bookmakers"]:
                        for m in bm["markets"]:
                            if m["key"]=="h2h":
                                for o in m["outcomes"]:
                                    odds[o["name"]]=max(odds.get(o["name"],0),o["price"])
                    
                    # VALUE PICK
                    val_pick = generate_pick({
                        "home": e["home_team"],
                        "away": e["away_team"],
                        "league": league,
                        "odds": {"home": odds.get(e["home_team"]),
                                 "away": odds.get(e["away_team"]),
                                 "draw": odds.get("Draw")}
                    })

                    if val_pick:
                        # Sprawdzenie duplikatów
                        if not any(c for c in coupons if c["home"]==e["home_team"] and c["away"]==e["away_team"] and c.get("type")=="value" and c["sent_date"]==str(now.date())):
                            stake = calc_kelly_stake(bankroll,val_pick["odds"],val_pick["val"])
                            bankroll -= stake
                            save_bankroll(bankroll)

                            val_match = {
                                "home": e["home_team"],
                                "away": e["away_team"],
                                "league": league,
                                "pick": val_pick["pick"],
                                "odds": val_pick["odds"],
                                "edge": val_pick["val"],
                                "stake": stake,
                                "dt": dt.isoformat(),
                                "type": "value",
                                "sent_date": str(now.date())
                            }
                            coupons.append(val_match)
                            value_matches.append(val_match)

                    # BTTS/OVER (przykład)
                    # Tutaj możesz rozszerzyć własną logikę BTTS/Over
                    btts_odds = odds.get(e["home_team"])  # przykładowo
                    if btts_odds:
                        if not any(c for c in coupons if c["home"]==e["home_team"] and c["away"]==e["away_team"] and c.get("type")=="btts_over" and c["sent_date"]==str(now.date())):
                            stake = round(bankroll*0.03,2)
                            bankroll -= stake
                            save_bankroll(bankroll)

                            btts_match = {
                                "home": e["home_team"],
                                "away": e["away_team"],
                                "league": league,
                                "pick": "BTTS/Over",
                                "odds": round(btts_odds,2),
                                "stake": stake,
                                "dt": dt.isoformat(),
                                "type": "btts_over",
                                "sent_date": str(now.date())
                            }
                            coupons.append(btts_match)
                            btts_matches.append(btts_match)

                break
            except: continue

    save_json(COUPONS_FILE,coupons)

    # Wysyłka telegram
    if value_matches:
        send_msg(format_value_card(value_matches[0]["league"], value_matches))
    if btts_matches:
        send_msg(format_btts_card(btts_matches))

# ================= MAIN =================
if __name__=="__main__":
    run()