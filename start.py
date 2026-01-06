import requests
import json
import os
from datetime import datetime, timedelta, timezone
from dateutil import parser

# ================= KONFIGURACJA =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")  # Kanał na TYPY
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS")  # Kanał na WYNIKI i RAPORTY

KEYS_POOL = [os.getenv("ODDS_KEY"), os.getenv("ODDS_KEY_2"), os.getenv("ODDS_KEY_3")]
API_KEYS = [k for k in KEYS_POOL if k]

COUPONS_FILE = "coupons.json"
STAKE = 5.0
MAX_HOURS_AHEAD = 48
VALUE_THRESHOLD = 0.03
MIN_ODDS = 2.5

LEAGUES = [
    "soccer_epl", "soccer_spain_la_liga", "soccer_italy_serie_a",
    "soccer_germany_bundesliga", "soccer_france_ligue_one",
    "basketball_nba", "soccer_netherlands_eredivisie", 
    "soccer_portugal_primeira_liga", "icehockey_nhl", "soccer_italy_serie_b"
]

LEAGUE_INFO = {
    "soccer_epl": {"name": "Premier League", "flag": "🏴󠁧󠁢󠁥󠁮󠁧󠁿"},
    "soccer_spain_la_liga": {"name": "La Liga", "flag": "🇪🇸"},
    "soccer_italy_serie_a": {"name": "Serie A", "flag": "🇮🇹"},
    "soccer_italy_serie_b": {"name": "Serie B", "flag": "🇮🇹"},
    "basketball_nba": {"name": "NBA", "flag": "🏀"},
    "icehockey_nhl": {"name": "NHL", "flag": "🏒"}
}

DYNAMIC_FORMS = {}
LAST_MATCH_TIME = {}

# ================= KOMUNIKACJA =================
def send_msg(text, target="types"):
    chat_id = T_CHAT_RESULTS if target == "results" else T_CHAT
    if not T_TOKEN or not chat_id: return
    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    try: requests.post(url, json=payload, timeout=15)
    except: pass

# ================= DATA MANAGEMENT =================
def load_coupons():
    if os.path.exists(COUPONS_FILE):
        try:
            with open(COUPONS_FILE, "r", encoding="utf-8") as f: return json.load(f)
        except: return []
    return []

def save_coupons(coupons):
    with open(COUPONS_FILE, "w", encoding="utf-8") as f:
        json.dump(coupons[-2000:], f, indent=4)

# ================= LOGIKA ANALITYCZNA =================
def fetch_real_team_forms():
    new_forms, last_times = {}, {}
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
    weights = [1, 1.1, 1.2, 1.3, 1.4][-len(res):]
    return sum(r * w for r, w in zip(res, weights)) / sum(weights)

def generate_pick(match):
    h_o, a_o, d_o = match["odds"]["home"], match["odds"]["away"], match["odds"].get("draw")
    if not h_o or not a_o: return None
    
    raw_sum = (1/h_o + 1/a_o + (1/d_o if d_o else 0))
    p_h, p_a = (1/h_o)/raw_sum, (1/a_o)/raw_sum
    p_d = ((1/d_o)/raw_sum) if d_o else 0
    
    f_h, f_a = get_team_form(match["home"]), get_team_form(match["away"])
    
    final_h = (0.20 * f_h) + (0.80 * p_h) + 0.03 # Home Bonus
    final_a = (0.20 * f_a) + (0.80 * p_a) - 0.03
    final_d = (0.20 * 0.5) + (0.80 * p_d) if d_o else 0

    # Kara B2B
    m_start = parser.isoparse(match["commence_time"])
    for team in [match["home"], match["away"]]:
        last_m = LAST_MATCH_TIME.get(team)
        if last_m and (m_start - last_m).total_seconds() < 108000:
            penalty = 0.04
            if team == match["home"]: final_h -= penalty; final_a += penalty
            else: final_a -= penalty; final_h += penalty

    opts = []
    if h_o >= MIN_ODDS: opts.append({"sel": match["home"], "odds": h_o, "val": final_h - (1/h_o)})
    if a_o >= MIN_ODDS: opts.append({"sel": match["away"], "odds": a_o, "val": final_a - (1/a_o)})
    if d_o and d_o >= MIN_ODDS: opts.append({"sel": "Remis", "odds": d_o, "val": final_d - (1/d_o)})
    
    if not opts: return None
    best = max(opts, key=lambda x: x['val'])
    return best if best['val'] >= VALUE_THRESHOLD else None

# ================= ROZLICZENIA I RAPORTY =================
def check_results():
    coupons = load_coupons()
    pending = [c for c in coupons if c["status"] == "pending"]
    if not pending: return
    
    for league in LEAGUES:
        for api_key in API_KEYS:
            try:
                url = f"https://api.the-odds-api.com/v4/sports/{league}/scores"
                r = requests.get(url, params={"apiKey": api_key, "daysFrom": 3}, timeout=15)
                if r.status_code != 200: continue
                results = r.json()
                for c in pending:
                    if c["league"] != league: continue
                    match = next((m for m in results if m["home_team"] == c["home"] and m["away_team"] == c["away"] and m.get("completed")), None)
                    if match:
                        scores = {s["name"]: int(s["score"]) for s in match["scores"]}
                        h_s, a_s = scores.get(c["home"], 0), scores.get(c["away"], 0)
                        
                        winner = "Remis"
                        if h_s > a_s: winner = c["home"]
                        elif a_s > h_s: winner = c["away"]
                        
                        if c["picked"] == winner:
                            c["status"], c["win_val"] = "won", round(c["odds"] * c["stake"], 2)
                            icon, note = "✅", f"Wygrana: {c['win_val']} PLN"
                        else:
                            c["status"], c["win_val"] = "lost", 0
                            icon, note = "❌", "Przegrana"
                        
                        send_msg(f"{icon} <b>ROZLICZENIE</b>\n{c['home']} - {c['away']}\nTyp: {c['picked']}\nWynik: {h_s}:{a_s}\n{note}", target="results")
                break
            except: continue
    save_coupons(coupons)

def send_weekly_report():
    now = datetime.now()
    if now.weekday() != 0 or now.hour != 9: return # Tylko poniedziałki o 9:00
    
    coupons = load_coupons()
    last_week = datetime.now(timezone.utc) - timedelta(days=7)
    week_data = [c for c in coupons if c["status"] != "pending" and parser.isoparse(c["date"]) > last_week]
    
    if not week_data: return
    
    total_staked = sum(c["stake"] for c in week_data)
    total_won = sum(c["win_val"] for c in week_data)
    profit = round(total_won - total_staked, 2)
    yield_val = round((profit / total_staked * 100), 2) if total_staked > 0 else 0
    
    msg = (f"📈 <b>RAPORT TYGODNIOWY</b>\n\n"
           f"💰 Postawiono: <b>{total_staked:.2f} PLN</b>\n"
           f"💵 Wygrano: <b>{total_won:.2f} PLN</b>\n"
           f"📊 Wynik: <b>{'+' if profit > 0 else ''}{profit} PLN</b>\n"
           f"🎯 Yield: <b>{yield_val}%</b>")
    send_msg(msg, target="results")

# ================= PROCES GŁÓWNY =================
def run():
    global DYNAMIC_FORMS, LAST_MATCH_TIME
    check_results() # Najpierw rozliczamy stare
    send_weekly_report() # Sprawdzamy czy czas na raport
    
    DYNAMIC_FORMS, LAST_MATCH_TIME = fetch_real_team_forms()
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
                    
                    # Pobieranie kursów
                    bm = event.get("bookmakers")
                    if not bm: continue
                    odds_list = bm[0]["markets"][0]["outcomes"]
                    h_o = next((o["price"] for o in odds_list if o["name"] == event["home_team"]), None)
                    a_o = next((o["price"] for o in odds_list if o["name"] == event["away_team"]), None)
                    d_o = next((o["price"] for o in odds_list if o["name"] == "Draw"), None)
                    
                    pick = generate_pick({"home": event["home_team"], "away": event["away_team"], "league": league, "odds": {"home": h_o, "away": a_o, "draw": d_o}, "commence_time": event["commence_time"]})
                    if pick:
                        pick.update({"m": event, "league": league, "m_dt": m_dt})
                        all_picks.append(pick)
                break
            except: continue

    # Selekcja NHL Top 5 + Reszta
    nhl = sorted([p for p in all_picks if p["league"] == "icehockey_nhl"], key=lambda x: x["val"], reverse=True)[:5]
    others = [p for p in all_picks if p["league"] != "icehockey_nhl"]
    
    for p in (nhl + others):
        m = p["m"]
        edge_pct = round(p["val"] * 100, 2)
        
        coupons.append({
            "home": m["home_team"], "away": m["away_team"], "picked": p["sel"],
            "odds": p["odds"], "stake": STAKE, "status": "pending",
            "date": m["commence_time"], "league": p["league"], "win_val": 0
        })
        
        info = LEAGUE_INFO.get(p["league"], {"name": p["league"], "flag": "⚽"})
        send_msg(f"{info['flag']} <b>NOWA OFERTA</b> ({info['name']})\n"
                 f"🏟️ {m['home_team']} - {m['away_team']}\n"
                 f"🎯 Typ: <b>{p['sel']}</b> | Kurs: <b>{p['odds']}</b>\n"
                 f"📊 Edge: <b>+{edge_pct}%</b>")
    
    save_coupons(coupons)

if __name__ == "__main__":
    run()
