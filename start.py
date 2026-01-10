import requests, json, os, sys
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from dateutil import parser

# ================= CONFIG =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS")

API_KEYS = [k for k in [
    os.getenv("ODDS_KEY"), os.getenv("ODDS_KEY_2"), os.getenv("ODDS_KEY_3"),
    os.getenv("ODDS_KEY_4"), os.getenv("ODDS_KEY_5")
] if k]

START_BANKROLL = 10000.0
BANKROLL_FILE = "bankroll.json"
COUPONS_FILE = "coupons.json"
TAX_PL = 0.88

LEAGUES = {
    "basketball_nba": "🏀 NBA", "icehockey_nhl": "🏒 NHL", "soccer_epl": "⚽ EPL",
    "soccer_germany_bundesliga": "⚽ Bundesliga", "soccer_italy_serie_a": "⚽ Serie A",
    "soccer_spain_la_liga": "⚽ La Liga", "soccer_france_ligue_one": "⚽ Ligue 1",
    "soccer_poland_ekstraklasa": "⚽ Ekstraklasa", "basketball_euroleague": "🇪🇺 Euroliga",
    "soccer_uefa_champions_league": "🏆 Champions League", "americanfootball_nfl": "🏈 NFL"
}

USA_LEAGUES = ["basketball_nba", "icehockey_nhl", "americanfootball_nfl"]

def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f: return json.load(f)
        except: pass
    return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f: json.dump(data, f, indent=2)

def send_msg(txt):
    if not T_TOKEN or not T_CHAT: return
    try: requests.post(f"https://api.telegram.org/bot{T_TOKEN}/sendMessage", 
                     json={"chat_id": T_CHAT, "text": txt, "parse_mode": "HTML"})
    except: pass

def no_vig_probs(odds):
    inv = {k: 1/v for k, v in odds.items() if v}
    s = sum(inv.values())
    return {k: v/s for k, v in inv.items()}

def run():
    only_usa = "--usa-only" in sys.argv
    now = datetime.now(timezone.utc)
    coupons = load_json(COUPONS_FILE, [])
    bankroll = load_json(BANKROLL_FILE, {"bankroll": START_BANKROLL})["bankroll"]
    
    for l_key, l_name in LEAGUES.items():
        if only_usa and l_key not in USA_LEAGUES: continue
        print(f"\n[ANALIZA] {l_name}")
        
        for key in API_KEYS:
            try:
                r = requests.get(f"https://api.the-odds-api.com/v4/sports/{l_key}/odds",
                               params={"apiKey": key, "markets": "h2h", "regions": "eu"}, timeout=15)
                if r.status_code != 200: continue
                
                events = r.json()
                for e in events:
                    dt = parser.isoparse(e["commence_time"])
                    if not (now <= dt <= now + timedelta(hours=72)): continue
                    
                    odds_map = defaultdict(list)
                    for bm in e["bookmakers"]:
                        for m in bm["markets"]:
                            for o in m["outcomes"]: odds_map[o["name"]].append(o["price"])
                    
                    odds = {n: max(l) for n, l in odds_map.items() if len(l) >= 2}
                    if len(odds) < 2: continue
                    
                    probs = no_vig_probs(odds)
                    for sel, prob in probs.items():
                        o = odds[sel]
                        edge = (prob - 1/(o * TAX_PL))
                        thr = 0.005 if l_key in USA_LEAGUES else 0.02
                        
                        # --- LUPA: To zobaczysz w logach Actions ---
                        print(f"  > {e['home_team']} - {sel}: Edge {round(edge*100,2)}% (Wymagane: {round(thr*100,2)}%)")
                        
                        if edge < thr: continue
                        if any(c["home"] == e["home_team"] for c in coupons): continue
                        
                        stake = round(min(bankroll * 0.02, 100), 2) # Prosta stawka 2% bankrollu
                        bankroll -= stake
                        win = round(stake * o * TAX_PL, 2)
                        
                        coupons.append({"league": l_key, "home": e["home_team"], "away": e["away_team"], 
                                      "pick": sel, "odds": o, "stake": stake, "possible_win": win, 
                                      "status": "PENDING", "date_time": dt.isoformat()})
                        
                        send_msg(f"⚔️ <b>VALUE BET ({l_name})</b>\n{e['home_team']} vs {e['away_team']}\nTyp: <b>{sel}</b> @{o}\nEdge: {round(edge*100,2)}%\nStawka: {stake} PLN")
                break
            except: continue
            
    save_json(COUPONS_FILE, coupons)
    save_json(BANKROLL_FILE, {"bankroll": round(bankroll, 2)})

if __name__ == "__main__":
    run()
