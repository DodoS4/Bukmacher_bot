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

# Filtry pod wysokie kursy (Underdog Hunter)
MIN_ODDS = 2.5
MAX_ODDS = 999.0 
VALUE_THRESHOLD = 0.03 

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
LAST_MATCH_TIME = {}

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

# ================= LOGIKA MATEMATYCZNA =================
def fetch_real_team_forms():
    new_forms = {}
    last_times = {}
    for league in LEAGUES:
        for api_key in API_KEYS:
            try:
                url = f"https://api.the-odds-api.com/v4/sports/{league}/scores"
                r = requests.get(url, params={"apiKey": api_key, "daysFrom": 14}, timeout=15)
                if r.status_code != 200: continue
                data = r.json()
                for match in data:
                    h_t, a_t = match["home_team"], match["away_team"]
                    m_time = parser.isoparse(match["commence_time"])
                    for team in [h_t, a_t]:
                        if team not in last_times or m_time > last_times[team]:
                            last_times[team] = m_time
                    if not match.get("completed"): continue
                    scores = {s["name"]: int(s["score"]) for s in match["scores"]}
                    h_s, a_s = scores.get(h_t, 0), scores.get(a_t, 0)
                    if h_t not in new_forms: new_forms[h_t] = []
                    if a_t not in new_forms: new_forms[a_t] = []
                    if h_s > a_s: new_forms[h_t].append(1); new_forms[a_t].append(0)
                    elif a_s > h_s: new_forms[h_t].append(0); new_forms[a_t].append(1)
                    else: new_forms[h_t].append(0.5); new_forms[a_t].append(0.5)
                break 
            except: continue
    return new_forms, last_times

def get_team_form(team_name):
    res = DYNAMIC_FORMS.get(team_name, [])
    if not res: return 0.5
    # Twoja średnia ważona (1.0 - 1.4)
    weights = [1, 1.1, 1.2, 1.3, 1.4][-len(res):]
    return sum(r * w for r, w in zip(res, weights)) / sum(weights)

def generate_pick(match):
    h_o, a_o, d_o = match["odds"]["home"], match["odds"]["away"], match["odds"].get("draw")
    if not h_o or not a_o: return None
    
    # Prob rynkowe (bez marży)
    raw_sum = (1/h_o + 1/a_o + (1/d_o if d_o else 0))
    p_h, p_a = (1/h_o)/raw_sum, (1/a_o)/raw_sum
    p_d = ((1/d_o)/raw_sum) if d_o else 0
    
    f_h, f_a = get_team_form(match["home"]), get_team_form(match["away"])
    
    # Model 20/80
    final_h = (0.20 * f_h) + (0.80 * p_h)
    final_a = (0.20 * f_a) + (0.80 * p_a)
    final_d = (0.20 * 0.5) + (0.80 * p_d) if d_o else -1

    # Home Advantage Bonus (+3%)
    final_h += 0.03
    final_a -= 0.03

    # Kara B2B (Back-to-Back)
    match_start = parser.isoparse(match["commence_time"])
    b2b_penalty = 0.05 if match["league"] == "basketball_nba" else 0.03
    for team in [match["home"], match["away"]]:
        last_m = LAST_MATCH_TIME.get(team)
        if last_m and (match_start - last_m).total_seconds() < 108000:
            if team == match["home"]: final_h -= b2b_penalty; final_a += b2b_penalty
            else: final_a -= b2b_penalty; final_h += b2b_penalty

    options = []
    if h_o >= MIN_ODDS: options.append({"sel": match["home"], "odds": h_o, "val": final_h - (1/h_o)})
    if a_o >= MIN_ODDS: options.append({"sel": match["away"], "odds": a_o, "val": final_a - (1/a_o)})
    if d_o and d_o >= MIN_ODDS: options.append({"sel": "Draw", "odds": d_o, "val": final_d - (1/d_o)})
    
    if not options: return None
    best = max(options, key=lambda x: x['val'])
    if best['val'] < VALUE_THRESHOLD: return None
    return {"selection": best['sel'], "odds": best['odds'], "val": best['val']}

# ================= PROCESY GŁÓWNE =================
def maintenance_tasks():
    coupons = load_coupons()
    if not coupons: return
    now = datetime.now(timezone.utc)
    # Usuwanie rekordów starszych niż 7 dni
    cleaned = [c for c in coupons if parser.isoparse(c["date"]) > now - timedelta(days=7)]
    if len(cleaned) < len(coupons): save_coupons(cleaned)

def simulate_offers():
    coupons = load_coupons()
    now = datetime.now(timezone.utc)
    all_picks = []
    
    for league in LEAGUES:
        for api_key in API_KEYS:
            try:
                url = f"https://api.the-odds-api.com/v4/sports/{league}/odds"
                r = requests.get(url, params={"apiKey": api_key, "regions": "eu", "markets": "h2h"}, timeout=15)
                if r.status_code != 200: continue
                for event in r.json():
                    m_dt = parser.isoparse(event["commence_time"])
                    if m_dt < now or m_dt > now + timedelta(hours=MAX_HOURS_AHEAD): continue
                    if any(c["home"] == event["home_team"] and c["away"] == event["away_team"] for c in coupons): continue
                    
                    # Wyciąganie kursów
                    h_o = a_o = d_o = None
                    if not event.get("bookmakers"): continue
                    outcomes = event["bookmakers"][0]["markets"][0]["outcomes"]
                    for o in outcomes:
                        if o["name"] == event["home_team"]: h_o = o["price"]
                        elif o["name"] == event["away_team"]: a_o = o["price"]
                        else: d_o = o["price"]
                    
                    if league == "icehockey_nhl": d_o = None
                    
                    m_data = {"home": event["home_team"], "away": event["away_team"], "league": league, "odds": {"home": h_o, "away": a_o, "draw": d_o}, "commence_time": event["commence_time"]}
                    pick = generate_pick(m_data)
                    if pick:
                        pick.update({"m": m_data, "league": league, "m_dt": m_dt})
                        all_picks.append(pick)
                break
            except: continue

    # Selekcja TOP 5 NHL + Reszta
    nhl_p = [p for p in all_picks if p['league'] == "icehockey_nhl"]
    other_p = [p for p in all_picks if p['league'] != "icehockey_nhl"]
    nhl_p.sort(key=lambda x: x['val'], reverse=True)
    
    for p in (nhl_p[:5] + other_p):
        m, m_dt = p['m'], p['m_dt']
        edge_pct = round(p['val'] * 100, 2)
        
        b2b_alert = ""
        h_l, a_l = LAST_MATCH_TIME.get(m["home"]), LAST_MATCH_TIME.get(m["away"])
        if h_l and (m_dt - h_l).total_seconds() < 108000: b2b_alert = "\n⚠️ <i>Dom gra B2B!</i>"
        elif a_l and (m_dt - a_l).total_seconds() < 108000: b2b_alert = "\n⚠️ <i>Wyjazd gra B2B!</i>"

        coupons.append({"home": m["home"], "away": m["away"], "picked": p["selection"], "odds": p["odds"], "stake": STAKE, "status": "pending", "date": m["commence_time"], "league": p['league']})
        
        info = LEAGUE_INFO.get(p['league'], {"name": p['league'], "flag": "⚽"})
        prefix = "⭐️ TOP NHL" if p['league'] == "icehockey_nhl" else "✅ NOWA OFERTA"
        
        send_msg(f"{info['flag']} <b>{prefix}</b> ({info['name']})\n"
                 f"🏟️ {m['home']} vs {m['away']}{b2b_alert}\n"
                 f"🕓 {m_dt.strftime('%d-%m-%Y %H:%M')} UTC\n\n"
                 f"✅ Typ: <b>{p['selection']}</b>\n"
                 f"🎯 Kurs: <b>{p['odds']}</b>\n"
                 f"📊 Przewaga (Edge): <b>+{edge_pct}%</b>\n"
                 f"💰 Stawka: <b>{STAKE} PLN</b>")
    save_coupons(coupons)

def run():
    global DYNAMIC_FORMS, LAST_MATCH_TIME
    maintenance_tasks()
    DYNAMIC_FORMS, LAST_MATCH_TIME = fetch_real_team_forms()
    simulate_offers()

if __name__ == "__main__":
    run()
