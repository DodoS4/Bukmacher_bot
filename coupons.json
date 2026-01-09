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
    # Zamiana datetime na string przy zapisie
    def convert(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return obj
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

# ================= FORMAT =================
def format_match_time(dt):
    return dt.strftime("%d.%m.%Y • %H:%M UTC")

def format_value_card(league_key, home, away, dt, pick, odds, edge, stake):
    info = LEAGUE_INFO.get(league_key, {"name": league_key, "flag": "🎯"})
    tier = "A" if edge >= 0.08 else "B"
    return (
        f"{info['flag']} <b>VALUE BET • {info['name']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"<b>{home} vs {away}</b>\n"
        f"🕒 {format_match_time(dt)}\n"
        f"🎯 Typ: <b>{pick}</b>\n"
        f"📈 Kurs: <b>{odds}</b>\n"
        f"💎 Edge: <b>{round(edge*100,2)}%</b>\n"
        f"🏷 Tier: <b>{tier}</b>\n"
        f"💰 Stawka: <b>{stake} PLN</b>"
    )

def format_btts_over_card(league_key, home, away, dt, pick_type, pick, odds, edge, stake):
    info = LEAGUE_INFO.get(league_key, {"name": league_key, "flag": "🎯"})
    return (
        f"{info['flag']} <b>{pick_type} • {info['name']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"<b>{home} vs {away}</b>\n"
        f"🕒 {format_match_time(dt)}\n"
        f"🎯 Typ: <b>{pick}</b>\n"
        f"📈 Kurs: <b>{odds}</b>\n"
        f"💎 Edge: <b>{round(edge*100,2)}%</b>\n"
        f"💰 Stawka: <b>{stake} PLN</b>"
    )

# ================= ODDS =================
def no_vig_probs(odds):
    inv = {k: 1/v for k, v in odds.items() if v}
    s = sum(inv.values())
    return {k: v/s for k, v in inv.items()}

def generate_pick(match, market_type="value"):
    h_o = match["odds"].get("home")
    a_o = match["odds"].get("away")
    d_o = match["odds"].get("draw")
    
    if market_type=="value":
        # standard value
        probs = no_vig_probs({"home": h_o, "away": a_o, "draw": d_o})
        p = {match["home"]: probs["home"], match["away"]: probs["away"], "Remis": probs.get("draw",0)}
        best = None
        for sel, prob in p.items():
            odds = h_o if sel==match["home"] else a_o if sel==match["away"] else d_o
            if odds and odds >= MIN_ODDS.get(match["league"],2.5):
                edge = prob - (1/odds)
                if edge >= VALUE_THRESHOLD:
                    if not best or edge>best["val"]:
                        best={"sel":sel,"odds":odds,"val":edge}
        return best
    else:
        # BTTS/Over logic - prosty przykład
        # zakładamy, że match["odds"] zawiera 'btts' i 'over_2.5'
        picks=[]
        for key in ["btts","over_2.5"]:
            if match["odds"].get(key):
                odds = match["odds"][key]
                edge = 0.02  # minimalny edge
                picks.append({"type":"BTTS_OVER" if key=="btts" else "OVER", "sel":match[key], "odds":odds,"val":edge})
        return picks if picks else None

# ================= RUN =================
def run():
    coupons = load_json(COUPONS_FILE,[])
    bankroll = load_bankroll()
    now = datetime.now(timezone.utc)

    value_matches=[]
    btts_over_matches=[]

    for league in LEAGUES:
        for key in API_KEYS:
            try:
                r=requests.get(f"https://api.the-odds-api.com/v4/sports/{league}/odds",
                               params={"apiKey":key,"markets":"h2h,totals,btts","regions":"eu"},
                               timeout=10)
                if r.status_code!=200: continue

                for e in r.json():
                    dt=parser.isoparse(e["commence_time"])
                    if not(now<=dt<=now+timedelta(hours=MAX_HOURS_AHEAD)):
                        continue

                    # przygotowanie kursów
                    odds={}
                    for bm in e.get("bookmakers",[]):
                        for m in bm.get("markets",[]):
                            if m["key"]=="h2h":
                                for o in m["outcomes"]:
                                    odds[o["name"]]=max(odds.get(o["name"],0),o["price"])
                            elif m["key"]=="totals":
                                for o in m["outcomes"]:
                                    odds["over_2.5"]=o["price"]  # przykład
                                    e["over_2.5"]=e["home_team"] if o["name"].endswith(">2.5") else e["away_team"]
                            elif m["key"]=="btts":
                                for o in m["outcomes"]:
                                    odds["btts"]=o["price"]
                                    e["btts"]=e["home_team"] if o["name"]=="Yes" else e["away_team"]

                    # Value
                    pick = generate_pick({
                        "home":e["home_team"],
                        "away":e["away_team"],
                        "league":league,
                        "odds":{"home":odds.get(e["home_team"]),
                                "away":odds.get(e["away_team"]),
                                "draw":odds.get("Draw")}
                    },market_type="value")

                    if pick:
                        # unikamy duplikatów
                        if not any(c for c in coupons if c["home"]==e["home_team"] and c["away"]==e["away_team"] and c.get("type")=="value" and c["sent_date"]==str(now.date())):
                            value_matches.append({"league":league,"home":e["home_team"],"away":e["away_team"],"pick":pick,"dt":dt})

                    # BTTS/Over
                    btts_picks = generate_pick({"home":e["home_team"],"away":e["away_team"],"league":league,"odds":odds,"btts":e.get("btts"),"over_2.5":e.get("over_2.5")},market_type="btts_over")
                    if btts_picks:
                        for bp in btts_picks:
                            if not any(c for c in coupons if c["home"]==e["home_team"] and c["away"]==e["away_team"] and c.get("type")=="btts_over" and c["sent_date"]==str(now.date()) and c["picked"]==bp["sel"]):
                                btts_over_matches.append({"league":league,"home":e["home_team"],"away":e["away_team"],"pick":bp,"dt":dt})

                break
            except:
                continue

    # wysyłamy value
    for vm in value_matches:
        stake=calc_kelly_stake(bankroll,vm["pick"]["odds"],vm["pick"]["val"])
        bankroll-=stake
        save_bankroll(bankroll)

        coupons.append({
            "home":vm["home"],
            "away":vm["away"],
            "picked":vm["pick"]["sel"],
            "odds":vm["pick"]["odds"],
            "stake":stake,
            "league":vm["league"],
            "type":"value",
            "status":"pending",
            "win_val":0,
            "sent_date":str(now.date())
        })

        send_msg(format_value_card(vm["league"],vm["home"],vm["away"],vm["dt"],vm["pick"]["sel"],vm["pick"]["odds"],vm["pick"]["val"],stake))

    # wysyłamy BTTS/Over
    for bm in btts_over_matches:
        stake=calc_kelly_stake(bankroll,bm["pick"]["odds"],bm["pick"]["val"])
        bankroll-=stake
        save_bankroll(bankroll)

        coupons.append({
            "home":bm["home"],
            "away":bm["away"],
            "picked":bm["pick"]["sel"],
            "odds":bm["pick"]["odds"],
            "stake":stake,
            "league":bm["league"],
            "type":"btts_over",
            "status":"pending",
            "win_val":0,
            "sent_date":str(now.date())
        })

        send_msg(format_btts_over_card(bm["league"],bm["home"],bm["away"],bm["dt"],bm["pick"]["type"],bm["pick"]["sel"],bm["pick"]["odds"],bm["pick"]["val"],stake))

    save_json(COUPONS_FILE,coupons)

# ================= MAIN =================
if __name__=="__main__":
    run()