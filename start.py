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
DAILY_LIMIT = 30
STAKE = 5.0
MAX_HOURS_AHEAD = 48

# Filtry kursów
MIN_ODDS = 2.00
MAX_ODDS = 10.0
VALUE_THRESHOLD = 0.02 

LEAGUES = [
    "soccer_epl", "soccer_spain_la_liga", "soccer_italy_serie_a",
    "soccer_germany_bundesliga", "soccer_france_ligue_one",
    "basketball_nba", "soccer_netherlands_eredivisie", "soccer_portugal_primeira_liga"
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
}

DYNAMIC_FORMS = {}

# ================= TELEGRAM (HTML) =================
def send_msg(text, target="types"):
    chat_id = T_CHAT_RESULTS if target == "results" else T_CHAT
    if not T_TOKEN or not chat_id: return
    
    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id, 
        "text": text, 
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        r = requests.post(url, json=payload, timeout=15)
        if r.status_code != 200: print(f"Błąd TG: {r.text}")
    except Exception as e: print(f"Błąd sieci TG: {e}")

# ================= RAPORT SKUTECZNOŚCI =================
def send_daily_report():
    coupons = load_coupons()
    settled = [c for c in coupons if c.get("status") in ["win", "loss"]]
    
    if not settled:
        return

    total_stake = sum(c["stake"] for c in settled)
    total_win = sum(c["win_val"] for c in settled if c["status"] == "win")
    profit = total_win - total_stake
    win_rate = (len([c for c in settled if c["status"] == "win"]) / len(settled)) * 100
    yield_val = (profit / total_stake) * 100 if total_stake > 0 else 0

    icon = "📈" if profit >= 0 else "📉"
    
    text = (
        f"📊 <b>PODSUMOWANIE SKUTECZNOŚCI</b>\n\n"
        f"✅ Rozliczone kupony: <b>{len(settled)}</b>\n"
        f"🎯 Skuteczność: <b>{win_rate:.1f}%</b>\n"
        f"💰 Łączny profit: <b>{profit:+.2f} PLN</b> {icon}\n"
        f"💎 Yield: <b>{yield_val:+.2f}%</b>\n\n"
        f"<i>Wskaźniki obliczone na podstawie całej historii.</i>"
    )
    send_msg(text, target="results")

# ================= DYNAMICZNA FORMA =================
def fetch_real_team_forms():
    new_forms = {}
    for league in LEAGUES:
        for api_key in API_KEYS:
            try:
                url = f"https://api.the-odds-api.com/v4/sports/{league}/scores"
                params = {"apiKey": api_key, "daysFrom": 14}
                r = requests.get(url, params=params, timeout=15)
                if r.status_code != 200: continue
                
                data = r.json()
                for match in data:
                    if not match.get("completed") or not match.get("scores"): continue
                    h_team, a_team = match["home_team"], match["away_team"]
                    scores = {s["name"]: int(s["score"]) for s in match["scores"]}
                    h_s, a_s = scores.get(h_team, 0), scores.get(a_team, 0)

                    if h_team not in new_forms: new_forms[h_team] = []
                    if a_team not in new_forms: new_forms[a_team] = []

                    if h_s > a_s:
                        new_forms[h_team].append(1); new_forms[a_team].append(0)
                    elif a_s > h_s:
                        new_forms[h_team].append(0); new_forms[a_team].append(1)
                    else:
                        new_forms[h_team].append(0.5); new_forms[a_team].append(0.5)
                break 
            except: continue
    return new_forms

def get_team_form(team_name):
    results = DYNAMIC_FORMS.get(team_name, [])
    return sum(results)/len(results) if results else 0.5

# ================= PLIKI =================
def load_coupons():
    if os.path.exists(COUPONS_FILE):
        try:
            with open(COUPONS_FILE, "r", encoding="utf-8") as f: return json.load(f)
        except: return []
    return []

def save_coupons(coupons):
    with open(COUPONS_FILE, "w", encoding="utf-8") as f:
        json.dump(coupons[-1000:], f, indent=4) # Zwiększono historię do 1000

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
                h_o = a_o = d_o = None
                for o in outcomes:
                    if o["name"] == home: h_o = o["price"]
                    elif o["name"] == away: a_o = o["price"]
                    else: d_o = o["price"]
                matches.append({
                    "home": home, "away": away, "league": league,
                    "odds": {"home": h_o, "away": a_o, "draw": d_o},
                    "commence_time": event["commence_time"]
                })
            if matches: break
        except: continue
    return matches

def generate_pick(match):
    h_o = match["odds"]["home"]
    a_o = match["odds"]["away"]
    d_o = match["odds"].get("draw")
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
    
    if best['val'] < VALUE_THRESHOLD or best['odds'] > MAX_ODDS:
        return None

    return {"selection": best['sel'], "odds": best['odds']}

def simulate_offers():
    coupons = load_coupons()
    now = datetime.now(timezone.utc)
    for league in LEAGUES:
        matches = get_upcoming_matches(league)
        for m in matches:
            m_dt = parser.isoparse(m["commence_time"])
            if m_dt < now or m_dt > now + timedelta(hours=MAX_HOURS_AHEAD): continue
            if any(c["home"] == m["home"] and c["away"] == m["away"] for c in coupons): continue

            pick = generate_pick(m)
            if pick:
                win_val = round(pick['odds'] * STAKE, 2)
                new_c = {
                    "home": m["home"], "away": m["away"], "picked": pick["selection"],
                    "odds": pick["odds"], "stake": STAKE, "status": "pending",
                    "date": m["commence_time"], "win_val": win_val, "league": league
                }
                coupons.append(new_c)
                info = LEAGUE_INFO.get(league, {"name": league, "flag": "⚽"})
                text = (
                    f"{info['flag']} <b>NOWA OFERTA</b> ({info['name']})\n"
                    f"🏟️ {m['home']} vs {m['away']}\n"
                    f"🕓 {m_dt.strftime('%d-%m-%Y %H:%M')} UTC\n\n"
                    f"✅ Typ: <b>{pick['selection']}</b>\n"
                    f"🎯 Kurs: <b>{pick['odds']}</b>\n"
                    f"💵 Stawka: {STAKE} PLN\n"
                    f"💰 <b>Możliwa wygrana: {win_val} PLN</b>"
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
        if now < m_dt + timedelta(hours=4): continue
        for api_key in API_KEYS:
            try:
                url = f"https://api.the-odds-api.com/v4/sports/{c['league']}/scores"
                r = requests.get(url, params={"apiKey": api_key, "daysFrom": 3}, timeout=15)
                if r.status_code != 200: continue
                m_data = next((e for e in r.json() if e["home_team"]==c["home"] and e["away_team"]==c["away"]), None)
                if not m_data or not m_data.get("completed"): continue

                scores = {s["name"]: int(s["score"]) for s in m_data["scores"]}
                h_s, a_s = scores.get(c["home"], 0), scores.get(c["away"], 0)
                winner = c["home"] if h_s > a_s else c["away"] if a_s > h_s else "Draw"
                c["status"] = "win" if winner == c["picked"] else "loss"
                profit = round(c["win_val"] - c["stake"], 2) if c["status"] == "win" else -c["stake"]
                icon = "✅" if c["status"] == "win" else "❌"
                text = (
                    f"{icon} <b>KUPON ROZLICZONY</b>\n"
                    f"🏟️ {c['home']} vs {c['away']}\n"
                    f"🎯 Typ: {c['picked']}\n"
                    f"💰 Bilans: <b>{profit:+.2f} PLN</b>"
                )
                send_msg(text, target="results")
                updated = True
                break
            except: continue
    if updated: save_coupons(coupons)

def run():
    global DYNAMIC_FORMS
    print("Aktualizacja danych...")
    DYNAMIC_FORMS = fetch_real_team_forms()
    simulate_offers()
    check_results()
    send_daily_report() # Wywołanie raportu po każdym cyklu
    print("Cykl zakończony.")

if __name__ == "__main__":
    run()
