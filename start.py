import requests
import json
import os
from datetime import datetime, timedelta, timezone
from dateutil import parser

# ================= KONFIGURACJA EKSPERCKA =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS")

KEYS_POOL = [os.getenv("ODDS_KEY"), os.getenv("ODDS_KEY_2"), os.getenv("ODDS_KEY_3")]
API_KEYS = [k for k in KEYS_POOL if k]

COUPONS_FILE = "coupons.json"
INITIAL_BANKROLL = 100.0  # Kapitał startowy
KELLY_FRACTION = 0.1      # Bezpieczeństwo: używamy tylko 10% sugerowanej stawki Kelly'ego
MIN_STAKE = 2.0           # Minimalna stawka
MAX_STAKE_PCT = 0.15      # Maksymalnie 15% portfela na jeden zakład
MAX_HOURS_AHEAD = 48

# PARAMETRY JAKOŚCIOWE
VALUE_THRESHOLD = 0.05  
MIN_ODDS_SOCCER = 2.50  
MIN_ODDS_NHL = 2.30     

LEAGUES = [
    "icehockey_nhl", "basketball_nba", "soccer_epl", 
    "soccer_england_championship", "soccer_poland_ekstraklasa",
    "soccer_germany_bundesliga", "soccer_uefa_champs_league"
]

LEAGUE_INFO = {
    "icehockey_nhl": {"name": "NHL", "flag": "🏒"},
    "basketball_nba": {"name": "NBA", "flag": "🏀"},
    "soccer_epl": {"name": "Premier League", "flag": "🏴󠁧󠁢󠁥󠁮󠁧󠁿"},
    "soccer_england_championship": {"name": "Championship", "flag": "🏴󠁧󠁢󠁥󠁮󠁧󠁿"},
    "soccer_poland_ekstraklasa": {"name": "Ekstraklasa", "flag": "🇵🇱"},
    "soccer_germany_bundesliga": {"name": "Bundesliga", "flag": "🇩🇪"},
    "soccer_uefa_champs_league": {"name": "Champions League", "flag": "🏆"}
}

# ================= MODUŁ FINANSOWY =================
def get_current_bankroll():
    coupons = load_coupons()
    settled = [c for c in coupons if c["status"] in ["won", "lost"]]
    profit = sum(float(c["win_val"]) - float(c["stake"]) for c in settled)
    return INITIAL_BANKROLL + profit

def calculate_dynamic_stake(odds, edge, bankroll):
    # Wzór Kelly'ego: f = edge / (kurs - 1)
    kelly_suggested = (edge / (odds - 1)) * KELLY_FRACTION
    raw_stake = bankroll * kelly_suggested
    
    # Filtry bezpieczeństwa
    final_stake = max(MIN_STAKE, min(raw_stake, bankroll * MAX_STAKE_PCT))
    return round(final_stake, 2)

# ================= KOMUNIKACJA I DANE =================
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
        json.dump(coupons[-2000:], f, indent=4)

# ================= ANALIZA I FORMULA =================
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
                    scores_list = match.get("scores", [])
                    if not scores_list: continue
                    scores = {s["name"]: int(s["score"]) for s in scores_list}
                    h_s, a_s = scores.get(h_t, 0), scores.get(a_t, 0)
                    
                    if h_t not in new_forms: new_forms[h_t] = []
                    if a_t not in new_forms: new_forms[a_t] = []
                    if h_s > a_s: new_forms[h_t].append(1); new_forms[a_t].append(0)
                    elif a_s > h_s: new_forms[h_t].append(0); new_forms[a_t].append(1)
                    else: new_forms[h_t].append(0.5); new_forms[a_t].append(0.5)
                break 
            except: continue
    return new_forms, last_times

def generate_pick(match, dynamic_forms, last_times):
    h_o, a_o, d_o = match["odds"]["home"], match["odds"]["away"], match["odds"].get("draw")
    if not h_o or not a_o: return None
    
    curr_min = MIN_ODDS_NHL if match["league"] == "icehockey_nhl" else MIN_ODDS_SOCCER
    raw_sum = (1/h_o + 1/a_o + (1/d_o if d_o else 0))
    p_h, p_a = (1/h_o)/raw_sum, (1/a_o)/raw_sum
    p_d = ((1/d_o)/raw_sum) if d_o else 0
    
    # Prosta waga formy
    def get_f(t):
        f = dynamic_forms.get(t, [])
        return sum(f)/len(f) if f else 0.5

    f_h, f_a = get_f(match["home"]), get_f(match["away"])
    final_h = (0.15 * f_h) + (0.85 * p_h)
    final_a = (0.15 * f_a) + (0.85 * p_a)
    final_d = (0.15 * 0.5) + (0.85 * p_d) if d_o else 0

    opts = []
    if h_o >= curr_min: opts.append({"sel": match["home"], "odds": h_o, "val": final_h - (1/h_o)})
    if a_o >= curr_min: opts.append({"sel": match["away"], "odds": a_o, "val": final_a - (1/a_o)})
    if d_o and d_o >= MIN_ODDS_SOCCER: opts.append({"sel": "Remis", "odds": d_o, "val": final_d - (1/d_o)})
    
    if not opts: return None
    best = max(opts, key=lambda x: x['val'])
    return best if best['val'] >= VALUE_THRESHOLD else None

# ================= GŁÓWNA PĘTLA =================
def run():
    now_local = datetime.now()
    bankroll = get_current_bankroll()
    
    # 1. Raport poranny
    if now_local.hour == 8 and now_local.minute < 30:
        # Tutaj wywołanie Twojej funkcji generate_daily_report()
        pass

    # 2. Pobierz formę i skanuj kursy
    forms, times = fetch_real_team_forms()
    coupons = load_coupons()
    now_utc = datetime.now(timezone.utc)

    for league in LEAGUES:
        for api_key in API_KEYS:
            try:
                url = f"https://api.the-odds-api.com/v4/sports/{league}/odds"
                r = requests.get(url, params={"apiKey": api_key, "regions": "eu", "markets": "h2h"}, timeout=15)
                if r.status_code != 200: continue
                
                for event in r.json():
                    if any(c["home"] == event["home_team"] and c["away"] == event["away_team"] for c in coupons): continue
                    
                    bm = event.get("bookmakers")
                    if not bm: continue
                    o_l = bm[0]["markets"][0]["outcomes"]
                    h_o = next((o["price"] for o in o_l if o["name"] == event["home_team"]), None)
                    a_o = next((o["price"] for o in o_l if o["name"] == event["away_team"]), None)
                    d_o = next((o["price"] for o in o_l if o["name"] == "Draw"), None)
                    
                    match_data = {"home": event["home_team"], "away": event["away_team"], "league": league, "odds": {"home": h_o, "away": a_o, "draw": d_o}}
                    pick = generate_pick(match_data, forms, times)
                    
                    if pick:
                        # OBLICZANIE DYNAMICZNEJ STAWKI
                        stake = calculate_dynamic_stake(pick["odds"], pick["val"], bankroll)
                        
                        info = LEAGUE_INFO.get(league, {"name": league, "flag": "⚽"})
                        msg = (f"{info['flag']} <b>INVESTMENT ALERT</b> ({info['name']})\n"
                               f"🏟️ {event['home_team']} - {event['away_team']}\n\n"
                               f"✅ Typ: <b>{pick['sel']}</b>\n"
                               f"🎯 Kurs: <b>{pick['odds']}</b>\n"
                               f"📊 Edge: <b>+{round(pick['val']*100, 1)}%</b>\n"
                               f"💰 Stawka: <b>{stake} PLN</b> (Portfel: {round(bankroll, 2)})")
                        
                        send_msg(msg)
                        coupons.append({
                            "home": event["home_team"], "away": event["away_team"],
                            "picked": pick["sel"], "odds": pick["odds"], "stake": stake,
                            "status": "pending", "league": league, "win_val": 0
                        })
                break
            except: continue
    save_coupons(coupons)

if __name__ == "__main__":
    run()
