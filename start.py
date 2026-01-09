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
    os.getenv("ODDS_KEY_3"),
    os.getenv("ODDS_KEY_4"),
    os.getenv("ODDS_KEY_5")
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
    chat_id = T_CHAT_RESULTS if target=="results" else T_CHAT
    if not T_TOKEN or not chat_id:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode":"HTML","disable_web_page_preview":True},
            timeout=10
        )
    except:
        pass

# ================= FORMAT =================
def format_value_card(league_key, home, away, dt, picks):
    info = LEAGUE_INFO.get(league_key, {"name": league_key, "flag": "🎯"})
    msg = f"{info['flag']} <b>TYPU • {info['name']}</b>\n━━━━━━━━━━━━━━━━━━\n<b>{home} vs {away}</b>\n🕒 {dt.strftime('%d.%m.%Y • %H:%M UTC')}\n\n"
    for p in picks:
        tier = "A" if p["edge"]>=0.08 else "B"
        msg += f"🎯 Typ: <b>{p['sel']}</b>\n📈 Kurs: <b>{p['odds']}</b>\n💎 Edge: <b>+{round(p['edge']*100,2)}%</b>\n🏷 Tier: <b>{tier}</b>\n💰 Stawka: <b>{p['stake']} PLN</b>\n\n"
    return msg

# ================= ODDS =================
def no_vig_probs(odds):
    inv = {k:1/v for k,v in odds.items() if v}
    s = sum(inv.values())
    return {k:v/s for k,v in inv.items()}

def generate_pick(match):
    h_o = match["odds"]["home"]
    a_o = match["odds"]["away"]
    d_o = match["odds"].get("draw")

    picks = []
    # --- Value Bets ---
    if match["league"]=="icehockey_nhl":
        probs = no_vig_probs({"home":h_o,"away":a_o})
        p_dict = {match["home"]:probs["home"], match["away"]:probs["away"]}
    else:
        probs = no_vig_probs({"home":h_o,"away":a_o,"draw":d_o})
        p_dict = {match["home"]:probs["home"], match["away"]:probs["away"], "Remis":probs.get("draw",0)*0.9}

    min_odds = MIN_ODDS.get(match["league"],2.5)
    for sel, prob in p_dict.items():
        odds = h_o if sel==match["home"] else a_o if sel==match["away"] else d_o
        if odds and odds>=min_odds:
            edge = prob-(1/odds)
            if edge>=VALUE_THRESHOLD:
                picks.append({"sel":sel,"odds":odds,"edge":edge,"type":"value"})
    
    # --- BTTS / Over 2.5 (dynamiczne, soft Kelly) ---
    # Tu przykład uproszczony: traktujemy wszystkie mecze koszykarski i piłkarskie jako BTTS/Over
    picks.append({"sel":"BTTS","odds":2.0,"edge":0.02,"type":"btts_over"})
    picks.append({"sel":"Over 2.5","odds":2.0,"edge":0.02,"type":"btts_over"})
    
    return picks if picks else None

# ================= RESULTS =================
def check_results():
    coupons = load_json(COUPONS_FILE, [])
    bankroll = load_bankroll()
    for league in LEAGUES:
        for key in API_KEYS:
            try:
                r = requests.get(f"https://api.the-odds-api.com/v4/sports/{league}/scores",
                                 params={"apiKey":key,"daysFrom":3},timeout=10)
                if r.status_code!=200: continue
                for c in coupons:
                    if c["status"]!="pending" or c["league"]!=league: continue
                    m = next((x for x in r.json() if x["home_team"]==c["home"] and x["away_team"]==c["away"] and x.get("completed")), None)
                    if not m: continue
                    scores = {s["name"]:int(s["score"]) for s in m.get("scores",[])}
                    hs, as_ = scores.get(c["home"],0), scores.get(c["away"],0)
                    winner = c["home"] if hs>as_ else c["away"] if as_>hs else "Remis"
                    if winner==c["picked"]:
                        profit = round(c["stake"]*(c["odds"]-1),2)
                        bankroll += profit
                        c["status"]="won"
                        c["win_val"]=profit
                        icon="✅"
                    else:
                        c["status"]="lost"
                        c["win_val"]=0
                        icon="❌"
                    send_msg(f"{icon} <b>ROZLICZENIE</b>\n{c['home']} vs {c['away']}\nTyp: {c['picked']} | Stawka: {c['stake']} PLN", target="results")
                break
            except: continue
    save_bankroll(bankroll)
    save_json(COUPONS_FILE, coupons)

# ================= RUN =================
def run():
    check_results()
    coupons = load_json(COUPONS_FILE,[])
    bankroll = load_bankroll()
    now = datetime.now(timezone.utc)
    all_matches = []

    for league in LEAGUES:
        for key in API_KEYS:
            try:
                r = requests.get(f"https://api.the-odds-api.com/v4/sports/{league}/odds",
                                 params={"apiKey":key,"markets":"h2h","regions":"eu"},timeout=10)
                if r.status_code!=200: continue
                for e in r.json():
                    dt = parser.isoparse(e["commence_time"])
                    if not(now<=dt<=now+timedelta(hours=MAX_HOURS_AHEAD)): continue

                    odds = {}
                    for bm in e["bookmakers"]:
                        for m in bm["markets"]:
                            if m["key"]=="h2h":
                                for o in m["outcomes"]:
                                    odds[o["name"]] = max(odds.get(o["name"],0), o["price"])

                    picks = generate_pick({
                        "home": e["home_team"],
                        "away": e["away_team"],
                        "league": league,
                        "odds": {"home":odds.get(e["home_team"]),
                                 "away":odds.get(e["away_team"]),
                                 "draw":odds.get("Draw")}
                    })

                    if picks:
                        # sprawdzenie duplikatów
                        if any(c for c in coupons if c["home"]==e["home_team"] and c["away"]==e["away_team"] and c["sent_date"]==str(now.date())):
                            continue
                        # liczymy stake
                        for p in picks:
                            p["stake"] = calc_kelly_stake(bankroll,p["odds"],p["edge"])
                        all_matches.append((e,dt,league,picks))
                break
            except: continue

    # wysyłka na Telegram
    for e,dt,league,picks in sorted(all_matches,key=lambda x:max(p["edge"] for p in x[3]),reverse=True):
        for p in picks:
            bankroll -= p["stake"]
        save_bankroll(bankroll)
        coupons.append({
            "home": e["home_team"],
            "away": e["away_team"],
            "league": league,
            "picks": picks,
            "status": "pending",
            "sent_date": str(now.date())
        })
        send_msg(format_value_card(league,e["home_team"],e["away_team"],dt,picks))

    save_json(COUPONS_FILE,coupons)

# ================= MAIN =================
if __name__=="__main__":
    if "--stats" in sys.argv:
        # osobny stats.py lub start.py --stats
        from stats import main as send_stats
        send_stats()
    else:
        run()