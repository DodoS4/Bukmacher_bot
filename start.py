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
FORMS_FILE = "forms_cache.json"
DAILY_LIMIT = 20
STAKE = 5.0
MAX_HOURS_AHEAD = 48

LEAGUES = [
    "soccer_epl", "soccer_spain_la_liga", "soccer_italy_serie_a",
    "soccer_germany_bundesliga", "soccer_france_ligue_one",
    "basketball_nba", "soccer_netherlands_eredivisie", "soccer_portugal_primeira_liga"
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

DYNAMIC_FORMS = {}

# ================= DYNAMICZNA FORMA =================
def fetch_real_team_forms():
    new_forms = {}
    for league in LEAGUES:
        for api_key in API_KEYS:
            try:
                url = f"https://api.the-odds-api.com/v4/sports/{league}/scores"
                params = {"apiKey": api_key, "daysFrom": 3}
                r = requests.get(url, params=params, timeout=15)
                if r.status_code != 200: continue
                
                data = r.json()
                for match in data:
                    if not match.get("completed") or not match.get("scores"): continue
                    
                    h_team, a_team = match["home_team"], match["away_team"]
                    scores = {s["name"]: int(s["score"]) for s in match["scores"]}
                    h_score, a_score = scores.get(h_team, 0), scores.get(a_team, 0)

                    if h_team not in new_forms: new_forms[h_team] = []
                    if a_team not in new_forms: new_forms[a_team] = []

                    if h_score > a_score:
                        new_forms[h_team].append(1); new_forms[a_team].append(0)
                    elif a_score > h_score:
                        new_forms[h_team].append(0); new_forms[a_team].append(1)
                    else:
                        new_forms[h_team].append(0.5); new_forms[a_team].append(0.5)
                break 
            except: continue
    return new_forms

def get_team_form(team_name):
    results = DYNAMIC_FORMS.get(team_name, [])
    return sum(results)/len(results) if results else 0.5

# ================= NARZĘDZIA I TELEGRAM =================
def escape_md(text):
    if not isinstance(text, str): return str(text)
    chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in chars:
        text = text.replace(char, f"\\{char}")
    return text

def send_msg(text, target="types"):
    chat_id = T_CHAT_RESULTS if target=="results" else T_CHAT
    if not T_TOKEN or not chat_id: return
    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
    try:
        # MarkdownV2 wymaga bardzo dokładnego escapowania znaków
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "MarkdownV2"}
        requests.post(url, json=payload, timeout=15)
    except: pass

# ================= PLIKI =================
def load_coupons():
    if os.path.exists(COUPONS_FILE):
        try:
            with open(COUPONS_FILE, "r", encoding="utf-8") as f: return json.load(f)
        except: return []
    return []

def save_coupons(coupons):
    with open(COUPONS_FILE, "w", encoding="utf-8") as f:
        json.dump(coupons[-500:], f, indent=4)

# ================= LOGIKA MECZÓW =================
def get_upcoming_matches(league):
    matches = []
    for api_key in API_KEYS:
        try:
            url = f"https://api.the-odds-api.com/v4/sports/{league}/odds"
            params = {"apiKey": api_key, "regions": "eu", "markets": "h2h", "oddsFormat": "decimal"}
            r = requests.get(url, params=params, timeout=15)
            if r.status_code != 200: continue
            
            data = r.json()
            for event in data:
                if not event.get("bookmakers"): continue
                home, away = event["home_team"], event["away_team"]
                outcomes = event["bookmakers"][0]["markets"][0]["outcomes"]
                
                h_odds = a_odds = d_odds = None
                for o in outcomes:
                    if o["name"] == home: h_odds = o["price"]
                    elif o["name"] == away: a_odds = o["price"]
                    else: d_odds = o["price"]

                matches.append({
                    "home": home, "away": away, "league": league,
                    "odds": {"home": h_odds, "away": a_odds, "draw": d_odds},
                    "commence_time": event["commence_time"]
                })
            if matches: break
        except: continue
    return matches

def generate_pick(match):
    h_odds = match["odds"]["home"]
    a_odds = match["odds"]["away"]
    d_odds = match["odds"].get("draw")

    if not h_odds or not a_odds: return None

    raw_probs = [1/h_odds, 1/a_odds]
    if d_odds: raw_probs.append(1/d_odds)
    
    total = sum(raw_probs)
    p_h, p_a = (1/h_odds)/total, (1/a_odds)/total
    p_d = ((1/d_odds)/total) if d_odds else 0

    f_h, f_a = get_team_form(match["home"]), get_team_form(match["away"])
    
    final_h = (0.6 * f_h) + (0.4 * p_h)
    final_a = (0.6 * f_a) + (0.4 * p_a)
    final_d = (0.6 * 0.5) + (0.4 * p_d) if d_odds else -1

    val_h, val_a = final_h - (1/h_odds), final_a - (1/a_odds)
    val_d = (final_d - (1/d_odds)) if d_odds else -1

    max_val = max(val_h, val_a, val_d)
    if max_val <= 0.05: return None 

    if max_val == val_h: sel, odds = match["home"], h_odds
    elif max_val == val_a: sel, odds = match["away"], a_odds
    else: sel, odds = "Draw", d_odds

    return {"selection": sel, "odds": odds}

def simulate_offers():
    coupons = load_coupons()
    today_iso = datetime.now(timezone.utc).date().isoformat()
    if len([c for c in coupons if c.get("date", "")[:10] == today_iso]) >= DAILY_LIMIT:
        return

    now = datetime.now(timezone.utc)
    for league in LEAGUES:
        matches = get_upcoming_matches(league)
        for m in matches:
            m_dt = parser.isoparse(m["commence_time"])
            if m_dt < now or m_dt > now + timedelta(hours=MAX_HOURS_AHEAD): continue
            if any(c["home"] == m["home"] and c["away"] == m["away"] for c in coupons): continue

            pick = generate_pick(m)
            if pick:
                new_c = {
                    "home": m["home"], "away": m["away"], "picked": pick["selection"],
                    "odds": pick["odds"], "stake": STAKE, "status": "pending",
                    "date": m["commence_time"], "win_val": round(pick["odds"]*STAKE, 2), "league": league
                }
                coupons.append(new_c)
                
                # POPRAWKA BŁĘDU SYNTAX: Przygotowanie zmiennych przed f-stringiem
                info = LEAGUE_INFO.get(league, {"name": league, "flag": "⚽"})
                s_league = escape_md(info['name'])
                s_home = escape_md(m['home'])
                s_away = escape_md(m['away'])
                s_pick = escape_md(pick['selection'])
                s_date = escape_md(m_dt.strftime('%d-%m-%Y %H:%M'))
                s_odds = escape_md(str(pick['odds']))
                
                text = (
                    f"{info['flag']} *NOWA OFERTA* ({s_league})\n"
                    f"🏟️ {s_home} vs {s_away}\n"
                    f"🕓 {s_date} UTC\n"
                    f"✅ Typ: *{s_pick}*\n"
                    f"💰 Stawka: {STAKE} PLN\n"
                    f"🎯 Kurs: {s_odds}"
                )
                send_msg(text)
    save_coupons(coupons)

def check_results():
    coupons = load_coupons()
    updated = False
    now = datetime.now(timezone.utc)

    for c in coupons:
        if c.get("status") != "pending": continue
        m_dt = parser.isoparse(c["date"])
        # Czekaj min. 4h od rozpoczęcia meczu
        if now < m_dt + timedelta(hours=4): continue

        for api_key in API_KEYS:
            try:
                url = f"https://api.the-odds-api.com/v4/sports/{c['league']}/scores"
                params = {"apiKey": api_key, "daysFrom": 3}
                r = requests.get(url, params=params, timeout=15)
                if r.status_code != 200: continue
                
                m_data = next((e for e in r.json() if e["home_team"]==c["home"] and e["away_team"]==c["away"]), None)
                if not m_data or not m_data.get("completed"): continue

                scores = {s["name"]: int(s["score"]) for s in m_data["scores"]}
                h_s, a_s = scores.get(c["home"], 0), scores.get(c["away"], 0)
                
                winner = c["home"] if h_s > a_s else c["away"] if a_s > h_s else "Draw"
                c["status"] = "win" if winner == c["picked"] else "loss"
                profit = round(c["win_val"] - c["stake"], 2) if c["status"] == "win" else -c["stake"]
                
                icon = "✅" if c["status"] == "win" else "❌"
                s_home = escape_md(c['home'])
                s_away = escape_md(c['away'])
                s_pick = escape_md(c['picked'])
                s_profit = escape_md(f"{profit:+.2f}")
                
                text = (
                    f"{icon} *KUPON ROZLICZONY*\n"
                    f"🏟️ {s_home} vs {s_away}\n"
                    f"🎯 Typ: {s_pick}\n"
                    f"💰 Bilans: {s_profit} PLN"
                )
                send_msg(text, target="results")
                updated = True
                break
            except: continue

    if updated: save_coupons(coupons)

def run():
    global DYNAMIC_FORMS
    print("Aktualizacja formy...")
    DYNAMIC_FORMS = fetch_real_team_forms()
    print("Szukanie typów...")
    simulate_offers()
    print("Rozliczanie...")
    check_results()

if __name__ == "__main__":
    run()
