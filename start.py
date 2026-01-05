import requests
import json
import os
from datetime import datetime, timedelta, timezone
from dateutil import parser

# ================= KONFIGURACJA =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS")

KEYS_POOL = [
    os.getenv("ODDS_KEY"),
    os.getenv("ODDS_KEY_2"),
    os.getenv("ODDS_KEY_3"),
    os.getenv("ODDS_KEY_4"),
    os.getenv("ODDS_KEY_5")
]
API_KEYS = [k for k in KEYS_POOL if k]

COUPONS_FILE = "coupons.json"
DAILY_LIMIT = 20
STAKE = 5.0
MAX_HOURS_AHEAD = 48

LEAGUES = [
    "soccer_epl",
    "soccer_spain_la_liga",
    "soccer_italy_serie_a",
    "soccer_germany_bundesliga",
    "soccer_france_ligue_one",
    "basketball_nba",
    "soccer_netherlands_eredivisie",
    "soccer_portugal_primeira_liga"
]

LEAGUE_INFO = {
    "soccer_epl": {"name": "Premier League", "flag": "🏴"},
    "soccer_spain_la_liga": {"name": "La Liga", "flag": "🇪🇸"},
    "soccer_italy_serie_a": {"name": "Serie A", "flag": "🇮🇹"},
    "soccer_germany_bundesliga": {"name": "Bundesliga", "flag": "🇩🇪"},
    "soccer_france_ligue_one": {"name": "Ligue 1", "flag": "🇫🇷"},
    "basketball_nba": {"name": "NBA", "flag": "🏀"},
    "soccer_netherlands_eredivisie": {"name": "Eredivisie", "flag": "🇳🇱"},
    "soccer_portugal_primeira_liga": {"name": "Primeira Liga", "flag": "🇵🇹"},
}

# ================= PRZYKŁADOWA FORMA DRUŻYN =================
TEAM_FORMS = {
    "Manchester United": [1, 0.5, 1, 0, 1],
    "Liverpool": [1, 1, 0, 1, 0.5],
    "Real Madrid": [1, 1, 1, 0.5, 1],
    "Barcelona": [1, 0.5, 0.5, 1, 1],
}

def get_team_form(team_name):
    results = TEAM_FORMS.get(team_name, [0.5]*5)
    return sum(results)/len(results)

# ================= NARZĘDZIE ESCAPE =================
def escape_md(text):
    if not isinstance(text, str):
        return text
    return text.replace("_","\\_").replace("*","\\*").replace("[","\\[").replace("]","\\]").replace("`","\\`")

# ================= WYSYŁKA =================
def send_msg(text, target="types"):
    chat_id = T_CHAT_RESULTS if target=="results" else T_CHAT
    if not T_TOKEN or not chat_id:
        return
    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode":"Markdown"}, timeout=15)
    except:
        pass

# ================= COUPONS =================
def load_coupons():
    if os.path.exists(COUPONS_FILE):
        try:
            with open(COUPONS_FILE,"r",encoding="utf-8") as f:
                return json.load(f)
        except:
            return []
    return []

def save_coupons(coupons):
    with open(COUPONS_FILE,"w",encoding="utf-8") as f:
        json.dump(coupons[-500:], f, indent=4)

def daily_limit_reached(coupons):
    today = datetime.now(timezone.utc).date().isoformat()
    today_sent = [c for c in coupons if c.get("date","")[:10]==today]
    return len(today_sent) >= DAILY_LIMIT

# ================= POBIERANIE MECZÓW =================
def get_upcoming_matches(league):
    matches = []
    for api_key in API_KEYS:
        try:
            url = f"https://api.the-odds-api.com/v4/sports/{league}/odds"
            params = {"apiKey": api_key, "regions":"eu","markets":"h2h","oddsFormat":"decimal"}
            r = requests.get(url, params=params, timeout=15)
            if r.status_code != 200:
                continue
            data = r.json()
            for event in data:
                home = event["home_team"]
                away = event["away_team"]
                commence = event["commence_time"]
                if event.get("bookmakers"):
                    b = event["bookmakers"][0]
                    outcomes = b["markets"][0]["outcomes"]
                    draw_odds = None
                    for o in outcomes:
                        if o["name"].lower() in ["draw","remis","rem"]:
                            draw_odds = o["price"]
                    h_odds = outcomes[0]["price"]
                    a_odds = outcomes[1]["price"]
                    matches.append({
                        "home": home,
                        "away": away,
                        "odds": {"home": h_odds,"away": a_odds,"draw": draw_odds},
                        "commence_time": commence
                    })
            if matches:
                break
        except:
            continue
    return matches

# ================= GENEROWANIE TYPU =================
def generate_pick(match):
    home = match["home"]
    away = match["away"]
    h_odds = match["odds"]["home"]
    a_odds = match["odds"]["away"]
    d_odds = match["odds"].get("draw", None)

    home_form = get_team_form(home)
    away_form = get_team_form(away)

    prob_home = 1 / h_odds
    prob_away = 1 / a_odds
    prob_draw = 1 / d_odds if d_odds else 0

    total = prob_home + prob_away + prob_draw
    prob_home /= total
    prob_away /= total
    prob_draw /= total

    prob_home = 0.6*home_form + 0.4*prob_home
    prob_away = 0.6*away_form + 0.4*prob_away
    if d_odds:
        prob_draw = 0.6*0.5 + 0.4*prob_draw
    else:
        prob_draw = -1

    val_home = prob_home - 1/h_odds
    val_away = prob_away - 1/a_odds
    val_draw = prob_draw - 1/d_odds if d_odds else -1

    max_val = max(val_home, val_away, val_draw)
    if max_val <= 0:
        return None

    if max_val == val_home: selection = home
    elif max_val == val_away: selection = away
    else: selection = "draw"

    return {
        "selection": selection,
        "odds": h_odds if selection==home else a_odds if selection==away else d_odds,
        "date": match["commence_time"],
        "home": home,
        "away": away
    }

# ================= GENERUJ OFERTY =================
def simulate_offers():
    coupons = load_coupons()
    if daily_limit_reached(coupons):
        return

    now = datetime.now(timezone.utc)

    for league in LEAGUES:
        matches = get_upcoming_matches(league)
        if not matches:
            continue

        for match in matches:
            match_dt = parser.isoparse(match["commence_time"])
            if match_dt < now or match_dt > now + timedelta(hours=MAX_HOURS_AHEAD):
                continue
            if any(c["home"]==match["home"] and c["away"]==match["away"] for c in coupons):
                continue

            pick = generate_pick(match)
            if pick:
                coupon = {
                    "home": pick["home"],
                    "away": pick["away"],
                    "picked": pick["selection"],
                    "odds": pick["odds"],
                    "stake": STAKE,
                    "status": "pending",
                    "date": pick["date"],
                    "win_val": round(pick["odds"]*STAKE,2),
                    "league": league
                }
                coupons.append(coupon)

                match_dt_str = match_dt.strftime("%d-%m-%Y %H:%M UTC")
                league_info = LEAGUE_INFO.get(league, {"name": league, "flag": ""})
                text = (
                    f"{league_info['flag']} *NOWA OFERTA* ({league_info['name']})\n"
                    f"🏟️ {escape_md(pick['home'])} vs {escape_md(pick['away'])}\n"
                    f"🕓 {match_dt_str}\n"
                    f"✅ Twój typ: *{escape_md(pick['selection'])}*\n"
                    f"💰 Stawka: {STAKE} PLN\n"
                    f"🎯 Kurs: {pick['odds']}"
                )
                send_msg(text,target="types")

    save_coupons(coupons)

# ================= POBIERANIE WYNIKU MECZU =================
def get_match_result(match):
    for api_key in API_KEYS:
        try:
            url = f"https://api.the-odds-api.com/v4/sports/soccer/scores"
            params = {
                "apiKey": api_key,
                "date": match["date"][:10],
                "teams": f"{match['home']},{match['away']}"
            }
            r = requests.get(url, params=params, timeout=15)
            if r.status_code != 200:
                continue
            data = r.json()
            for e in data:
                if e["home_team"]==match["home"] and e["away_team"]==match["away"]:
                    home_score = e.get("home_score")
                    away_score = e.get("away_score")
                    if home_score is None or away_score is None:
                        return None
                    if home_score > away_score:
                        return "home"
                    elif away_score > home_score:
                        return "away"
                    else:
                        return "draw"
        except:
            continue
    return None

# ================= ROZLICZANIE =================
def check_results():
    coupons = load_coupons()
    updated = False
    now = datetime.now(timezone.utc)

    for c in coupons:
        if c.get("status") != "pending":
            continue

        match_dt = parser.isoparse(c["date"])
        if now < match_dt + timedelta(hours=4):
            continue

        result = get_match_result(c)
        if result is None:
            continue

        c["status"] = "win" if result == c["picked"] else "loss"
        profit = round(c["win_val"] - c["stake"],2) if c["status"]=="win" else -c["stake"]
        match_dt_str = match_dt.strftime("%d-%m-%Y %H:%M UTC")
        icon = "✅" if c["status"]=="win" else "❌"
        league_info = LEAGUE_INFO.get(c["league"], {"name": c["league"], "flag": ""})
        text = (
            f"{icon} *KUPON ROZLICZONY* ({league_info['name']})\n"
            f"🏟️ {escape_md(c['home'])} vs {escape_md(c['away'])}\n"
            f"🕓 {match_dt_str}\n"
            f"🎯 Twój typ: {escape_md(c['picked'])}\n"
            f"💰 Bilans: {profit:+.2f} PLN\n"
            f"🎯 Kurs: {c['odds']}"
        )
        send_msg(text, target="results")
        updated = True

    if updated:
        save_coupons(coupons)

# ================= START =================
def run():
    simulate_offers()
    check_results()

if __name__=="__main__":
    run()
