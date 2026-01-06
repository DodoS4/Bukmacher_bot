import requests
import json
import os
from datetime import datetime, timedelta, timezone
from dateutil import parser

# ================= KONFIGURACJA =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS")

KEYS_POOL = [os.getenv("ODDS_KEY"), os.getenv("ODDS_KEY_2"), os.getenv("ODDS_KEY_3"), os.getenv("ODDS_KEY_4"), os.getenv("ODDS_KEY_5")]
API_KEYS = [k for k in KEYS_POOL if k]

COUPONS_FILE = "coupons.json"
STAKE = 5.0
MAX_HOURS_AHEAD = 48

# Filtry kursów - BEZ LIMITU GÓRNEGO
MIN_ODDS = 2.00
MAX_ODDS = 999.0 
VALUE_THRESHOLD = 0.02 

LEAGUES = [
    "soccer_epl", "soccer_spain_la_liga", "soccer_italy_serie_a",
    "soccer_germany_bundesliga", "soccer_france_ligue_one",
    "basketball_nba", "soccer_netherlands_eredivisie", 
    "soccer_portugal_primeira_liga", "icehockey_nhl"
]

LEAGUE_INFO = {
    "soccer_epl": {"name": "Premier League", "flag": "🏴󠁧󠁢󠁥󠁮󠁧󠁿"},
    "soccer_spain_la_liga": {"name": "La Liga", "flag": "🇪🇸"},
    "soccer_italy_serie_a": {"name": "Serie A", "flag": "🇮🇹"},
    "soccer_germany_bundesliga": {"name": "Bundesliga", "flag": "🇩🇪"},
    "soccer_france_ligue_one": {"name": "Ligue 1", "flag": "🇫🇷"},
    "basketball_nba": {"name": "NBA", "flag": "🏀"},
    "soccer_netherlands_eredivisie": {"name": "Eredivisie", "flag": "🇳🇱"},
    "soccer_portugal_primeira_liga": {"name": "Primeira Liga", "flag": "🇵🇹"},
    "icehockey_nhl": {"name": "NHL", "flag": "🏒"}
}

DYNAMIC_FORMS = {}

# ================= POMOCNICZE =================
def send_msg(text, target="types"):
    chat_id = T_CHAT_RESULTS if target == "results" else T_CHAT
    if not T_TOKEN or not chat_id: return
    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    try: requests.post(url, json=payload, timeout=15)
    except: pass

def load_coupons():
    if os.path.exists(COUPONS_FILE):
        try:
            with open(COUPONS_FILE, "r", encoding="utf-8") as f: return json.load(f)
        except: return []
    return []

def save_coupons(coupons):
    with open(COUPONS_FILE, "w", encoding="utf-8") as f:
        json.dump(coupons[-1000:], f, indent=4) 

# ================= LOGIKA FORM I KURSÓW =================
def fetch_real_team_forms():
    new_forms = {}
    for league in LEAGUES:
        for api_key in API_KEYS:
            try:
                url = f"https://api.the-odds-api.com/v4/sports/{league}/scores"
                r = requests.get(url, params={"apiKey": api_key, "daysFrom": 14}, timeout=15)
                if r.status_code != 200: continue
                data = r.json()
                for match in data:
                    if not match.get("completed"): continue
                    h_t, a_t = match["home_team"], match["away_team"]
                    scores = {s["name"]: int(s["score"]) for s in match["scores"]}
                    h_s, a_s = scores.get(h_t, 0), scores.get(a_t, 0)
                    if h_t not in new_forms: new_forms[h_t] = []
                    if a_t not in new_forms: new_forms[a_t] = []
                    if h_s > a_s: new_forms[h_t].append(1); new_forms[a_t].append(0)
                    elif a_s > h_s: new_forms[h_t].append(0); new_forms[a_t].append(1)
                    else: new_forms[h_t].append(0.5); new_forms[a_t].append(0.5)
                break 
            except: continue
    return new_forms

def get_team_form(team_name):
    res = DYNAMIC_FORMS.get(team_name, [])
    return sum(res)/len(res) if res else 0.5

def get_upcoming_matches(league):
    matches = []
    for api_key in API_KEYS:
        try:
            url = f"https://api.the-odds-api.com/v4/sports/{league}/odds"
            params = {"apiKey": api_key, "regions": "eu", "markets": "h2h", "oddsFormat": "decimal"}
            r = requests.get(url, params=params, timeout=15)
            if r.status_code != 200: continue
            for event in r.json():
                if not event.get("bookmakers"): continue
                h, a = event["home_team"], event["away_team"]
                outcomes = event["bookmakers"][0]["markets"][0]["outcomes"]
                h_o = a_o = d_o = None
                for o in outcomes:
                    if o["name"] == h: h_o = o["price"]
                    elif o["name"] == a: a_o = o["price"]
                    else: d_o = o["price"]
                
                if league == "icehockey_nhl": d_o = None

                matches.append({"home": h, "away": a, "league": league, "odds": {"home": h_o, "away": a_o, "draw": d_o}, "commence_time": event["commence_time"]})
            if matches: break
        except: continue
    return matches

def generate_pick(match):
    h_o, a_o, d_o = match["odds"]["home"], match["odds"]["away"], match["odds"].get("draw")
    if not h_o or not a_o: return None
    raw_sum = (1/h_o + 1/a_o + (1/d_o if d_o else 0))
    p_h, p_a = (1/h_o)/raw_sum, (1/a_o)/raw_sum
    p_d = ((1/d_o)/raw_sum) if d_o else 0
    f_h, f_a = get_team_form(match["home"]), get_team_form(match["away"])
    final_h = (0.15 * f_h) + (0.85 * p_h)
    final_a = (0.15 * f_a) + (0.85 * p_a)
    final_d = (0.15 * 0.5) + (0.85 * p_d) if d_o else -1
    options = []
    if h_o >= MIN_ODDS: options.append({"sel": match["home"], "odds": h_o, "val": final_h - (1/h_o)})
    if a_o >= MIN_ODDS: options.append({"sel": match["away"], "odds": a_o, "val": final_a - (1/a_o)})
    if d_o and d_o >= MIN_ODDS: options.append({"sel": "Draw", "odds": d_o, "val": final_d - (1/d_o)})
    if not options: return None
    best = max(options, key=lambda x: x['val'])
    if best['val'] < VALUE_THRESHOLD or best['odds'] > MAX_ODDS: return None
    return {"selection": best['sel'], "odds": best['odds'], "val": best['val']}

# ================= SYMULACJA Z DATAMI DLA WSZYSTKICH LIG =================
def simulate_offers():
    coupons = load_coupons()
    now = datetime.now(timezone.utc)
    all_picks = []
    
    for league in LEAGUES:
        matches = get_upcoming_matches(league)
        for m in matches:
            m_dt = parser.isoparse(m["commence_time"])
            if m_dt < now or m_dt > now + timedelta(hours=MAX_HOURS_AHEAD): continue
            if any(c["home"] == m["home"] and c["away"] == m["away"] for c in coupons): continue
            
            pick = generate_pick(m)
            if pick:
                # Każdy pick teraz zawiera m_dt i dane meczu m
                pick.update({"m": m, "league": league, "m_dt": m_dt})
                all_picks.append(pick)

    # Logika Top 5 dla NHL
    nhl_picks = [p for p in all_picks if p['league'] == "icehockey_nhl"]
    other_picks = [p for p in all_picks if p['league'] != "icehockey_nhl"]
    
    nhl_picks.sort(key=lambda x: x['val'], reverse=True)
    final_nhl = nhl_picks[:5]
    
    # Połączone oferty (wszystkie mają teraz przypisane m_dt)
    final_selection = final_nhl + other_picks

    for p in final_selection:
        m = p['m']
        m_dt = p['m_dt']
        win_val = round(p['odds'] * STAKE, 2)
        coupons.append({"home": m["home"], "away": m["away"], "picked": p["selection"], "odds": p["odds"], "stake": STAKE, "status": "pending", "date": m["commence_time"], "win_val": win_val, "league": p['league']})
        
        info = LEAGUE_INFO.get(p['league'], {"name": p['league'], "flag": "⚽"})
        prefix = "⭐️ TOP NHL" if p['league'] == "icehockey_nhl" else "✅ NOWA OFERTA"
        
        # Data i godzina dla każdej ligi (Piłka, NBA, NHL)
        send_msg(f"{info['flag']} <b>{prefix}</b> ({info['name']})\n"
                 f"🏟️ {m['home']} vs {m['away']}\n"
                 f"🕓 {m_dt.strftime('%d-%m-%Y %H:%M')} UTC\n\n"
                 f"✅ Typ: <b>{p['selection']}</b>\n"
                 f"🎯 Kurs: <b>{p['odds']}</b>\n"
                 f"💰 Możliwa wygrana: <b>{win_val} PLN</b>")
    
    save_coupons(coupons)

def run():
    global DYNAMIC_FORMS
    DYNAMIC_FORMS = fetch_real_team_forms()
    simulate_offers()

if __name__ == "__main__":
    run()
