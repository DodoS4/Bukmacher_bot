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
INITIAL_BANKROLL = 100.0  # Twój startowy budżet
MAX_HOURS_AHEAD = 48

VALUE_THRESHOLD = 0.01  
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

# ================= INTELIGENTNE STAWKOWANIE =================
def calculate_smart_stake(edge, odds, current_bankroll):
    """Implementacja Fractional Kelly Criterion (B=0.1)"""
    # Kelly % = (Edge) / (Odds - 1)
    kelly_pct = edge / (odds - 1)
    # Stawiamy tylko 10% tego co sugeruje Kelly dla bezpieczeństwa (Fractional Kelly)
    safe_kelly = kelly_pct * 0.1 
    
    # Ograniczenia: min 2 PLN, max 10% całego budżetu na jeden mecz
    final_stake = current_bankroll * safe_kelly
    if final_stake < 2.0: final_stake = 2.0
    if final_stake > (current_bankroll * 0.10): final_stake = current_bankroll * 0.10
    
    return round(final_stake, 2)

# ================= STATYSTYKI I RAPORTY =================
def generate_daily_report():
    coupons = load_coupons()
    settled = [c for c in coupons if c["status"] in ["won", "lost"]]
    
    total_staked = sum(float(c["stake"]) for c in settled)
    total_won = sum(float(c["win_val"]) for c in settled)
    current_profit = round(total_won - total_staked, 2)
    current_bankroll = INITIAL_BANKROLL + current_profit
    yield_val = round((current_profit / total_staked * 100), 2) if total_staked > 0 else 0
    
    if not settled:
        return "📊 <b>RAPORT:</b> Czekam na pierwsze rozliczenia meczów."

    league_stats = {}
    for c in settled:
        l_name = LEAGUE_INFO.get(c.get("league"), {"name": "Inne"})["name"]
        if l_name not in league_stats: league_stats[l_name] = 0
        league_stats[l_name] += (float(c["win_val"]) - float(c["stake"]))

    sorted_leagues = sorted(league_stats.items(), key=lambda item: item[1], reverse=True)
    league_report = ""
    for name, l_profit in sorted_leagues:
        l_icon = "🟢" if l_profit >= 0 else "🔴"
        league_report += f"{l_icon} {name}: <b>{round(l_profit, 2)} PLN</b>\n"

    icon = "🚀" if current_profit >= 0 else "📉"
    
    report = (f"📊 <b>RAPORT PORTFELA (9.5/10)</b>\n\n"
              f"💰 Stan konta: <b>{round(current_bankroll, 2)} PLN</b>\n"
              f"{icon} Zysk netto: <b>{current_profit} PLN</b>\n"
              f"🎯 Yield: <b>{yield_val}%</b>\n"
              f"----------------------------\n"
              f"🏆 <b>ZYSKI WG LIG:</b>\n"
              f"{league_report}\n"
              f"<i>Algorytm Kelly'ego dba o Twoje ryzyko.</i>")
    return report

# ================= ZARZĄDZANIE DANYMI =================
def load_coupons():
    if os.path.exists(COUPONS_FILE):
        try:
            with open(COUPONS_FILE, "r", encoding="utf-8") as f: return json.load(f)
        except: return []
    return []

def save_coupons(coupons):
    with open(COUPONS_FILE, "w", encoding="utf-8") as f:
        json.dump(coupons[-2000:], f, indent=4)

# ================= ANALIZA I FORMALISTYKA =================
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

def get_team_form(team_name):
    res = DYNAMIC_FORMS.get(team_name, [])
    if not res: return 0.5
    weights = [1, 1.1, 1.2, 1.3, 1.4][-len(res):]
    return sum(r * w for r, w in zip(res, weights)) / sum(weights)

def generate_pick(match):
    h_o, a_o, d_o = match["odds"]["home"], match["odds"]["away"], match["odds"].get("draw")
    if not h_o or not a_o: return None
    
    curr_min = MIN_ODDS_NHL if match["league"] == "icehockey_nhl" else MIN_ODDS_SOCCER
    raw_sum = (1/h_o + 1/a_o + (1/d_o if d_o else 0))
    p_h, p_a = (1/h_o)/raw_sum, (1/a_o)/raw_sum
    p_d = ((1/d_o)/raw_sum) if d_o else 0
    
    f_h, f_a = get_team_form(match["home"]), get_team_form(match["away"])
    final_h = (0.20 * f_h) + (0.80 * p_h) + 0.02 
    final_a = (0.20 * f_a) + (0.80 * p_a) - 0.02
    final_d = (0.20 * 0.5) + (0.80 * p_d) if d_o else 0

    m_start = parser.isoparse(match["commence_time"])
    for team in [match["home"], match["away"]]:
        last_m = LAST_MATCH_TIME.get(team)
        if last_m and (m_start - last_m).total_seconds() < 108000:
            penalty = 0.03 
            if team == match["home"]: final_h -= penalty; final_a += penalty
            else: final_a -= penalty; final_h += penalty

    opts = []
    if h_o >= curr_min: opts.append({"sel": match["home"], "odds": h_o, "val": final_h - (1/h_o)})
    if a_o >= curr_min: opts.append({"sel": match["away"], "odds": a_o, "val": final_a - (1/a_o)})
    if d_o and d_o >= MIN_ODDS_SOCCER: opts.append({"sel": "Remis", "odds": d_o, "val": final_d - (1/d_o)})
    
    if not opts: return None
    best = max(opts, key=lambda x: x['val'])
    return best if best['val'] >= VALUE_THRESHOLD else None

# ================= ROZLICZENIA =================
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
                        scores_list = match.get("scores", [])
                        scores = {s["name"]: int(s["score"]) for s in scores_list}
                        h_s, a_s = scores.get(c["home"], 0), scores.get(c["away"], 0)
                        winner = "Remis"
                        if h_s > a_s: winner = c["home"]
                        elif a_s > h_s: winner = c["away"]
                        
                        if c["picked"] == winner:
                            c["status"], c["win_val"] = "won", round(c["odds"] * c["stake"], 2)
                            icon = "✅"
                        else:
                            c["status"], c["win_val"] = "lost", 0
                            icon = "❌"
                        
                        send_msg(f"{icon} <b>ROZLICZENIE</b>\n{c['home']} - {c['away']}\nWynik: {h_s}:{a_s}\nZysk: {round(c['win_val'] - c['stake'], 2)} PLN", target="results")
                break
            except: continue
    save_coupons(coupons)

# ================= URUCHOMIENIE =================
def run():
    global DYNAMIC_FORMS, LAST_MATCH_TIME
    check_results()
    
    coupons = load_coupons()
    settled = [c for c in coupons if c["status"] in ["won", "lost"]]
    current_bankroll = INITIAL_BANKROLL + sum(float(c["win_val"]) - float(c["stake"]) for c in settled)

    if datetime.now().hour == 8 and datetime.now().minute < 15:
        send_msg(generate_daily_report(), target="results")

    DYNAMIC_FORMS, LAST_MATCH_TIME = fetch_real_team_forms()
    now_utc = datetime.now(timezone.utc)
    all_picks = []

    for league in LEAGUES:
        for api_key in API_KEYS:
            try:
                url = f"https://api.the-odds-api.com/v4/sports/{league}/odds"
                r = requests.get(url, params={"apiKey": api_key, "regions": "eu", "markets": "h2h"}, timeout=15)
                if r.status_code != 200: continue
                for event in r.json():
                    m_dt = parser.isoparse(event["commence_time"])
                    if m_dt < now_utc or m_dt > now_utc + timedelta(hours=MAX_HOURS_AHEAD): continue
                    if any(c["home"] == event["home_team"] and c["away"] == event["away_team"] for c in coupons): continue
                    
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

    top_5 = sorted(all_picks, key=lambda x: x["val"], reverse=True)[:5]
    
    for p in top_5:
        edge_pct = round(p["val"] * 100, 2)
        dynamic_stake = calculate_smart_stake(p["val"], p["odds"], current_bankroll)
        info = LEAGUE_INFO.get(p["league"], {"name": p["league"], "flag": "⚽"})
        
        msg = (f"{info['flag']} <b>{info['name']}</b>\n"
               f"🏟️ {p['m']['home_team']} - {p['m']['away_team']}\n"
               f"✅ Typ: <b>{p['sel']}</b> | Kurs: <b>{p['odds']}</b>\n"
               f"📊 Przewaga: <b>+{edge_pct}%</b>\n"
               f"💰 Stawka: <b>{dynamic_stake} PLN</b>")
        
        send_msg(msg)
        coupons.append({"home": p['m']["home_team"], "away": p['m']["away_team"], "picked": p["sel"], "odds": p["odds"], "stake": dynamic_stake, "status": "pending", "date": p['m']["commence_time"], "league": p["league"], "win_val": 0})
    
    save_coupons(coupons)

if __name__ == "__main__":
    run()
