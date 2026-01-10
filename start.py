import requests, json, os, sys
from datetime import datetime, timezone, timedelta
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

START_BANKROLL = 10000.0
BANKROLL_FILE = "bankroll.json"
COUPONS_FILE = "coupons.json"

# Parametry strategii
MAX_HOURS_AHEAD = 72       
VALUE_THRESHOLD = 0.02     # 2% przewagi NETTO (po podatku)
ODDS_MIN = 1.5
ODDS_MAX = 10.0
MAX_BETS_PER_DAY = 10      
TAX_PL = 0.88              # Współczynnik po odliczeniu 12% podatku

LEAGUES = {
    "basketball_nba": "🏀 NBA",
    "icehockey_nhl": "🏒 NHL",
    "soccer_epl": "⚽ EPL",
    "soccer_germany_bundesliga": "⚽ Bundesliga",
    "soccer_italy_serie_a": "⚽ Serie A",
    "soccer_spain_la_liga": "⚽ La Liga",
    "soccer_france_ligue_one": "⚽ Ligue 1",
    "soccer_poland_ekstraklasa": "⚽ Ekstraklasa",
    "basketball_euroleague": "🇪🇺 Euroliga",
    "soccer_uefa_champions_league": "🏆 Champions League",
    "americanfootball_nfl": "🏈 NFL"
}

EDGE_MULTIPLIER = {
    "basketball_nba": 0.90,
    "icehockey_nhl": 0.90,
    "soccer_epl": 0.80,
    "soccer_germany_bundesliga": 0.75,
    "soccer_italy_serie_a": 0.75,
    "soccer_spain_la_liga": 0.75,
    "soccer_france_ligue_one": 0.70,
    "soccer_poland_ekstraklasa": 0.85,
    "basketball_euroleague": 0.80,
    "soccer_uefa_champions_league": 0.90,
    "americanfootball_nfl": 0.85
}

USA_LEAGUES = ["basketball_nba", "icehockey_nhl", "americanfootball_nfl"]

# ================= UTILS =================
def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def load_bankroll():
    data = load_json(BANKROLL_FILE, None)
    if not data:
        save_json(BANKROLL_FILE, {"bankroll": START_BANKROLL})
        return START_BANKROLL
    return data.get("bankroll", START_BANKROLL)

def save_bankroll(val):
    save_json(BANKROLL_FILE, {"bankroll": round(val, 2)})

def send_msg(txt, target="types"):
    chat = T_CHAT_RESULTS if target == "results" else T_CHAT
    if not T_TOKEN or not chat: return
    try:
        requests.post(
            f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
            json={"chat_id": chat, "text": txt, "parse_mode": "HTML"},
            timeout=10
        )
    except: pass

def calc_kelly(bankroll, odds, edge, kelly_frac, max_pct):
    if edge <= 0 or odds <= 1: return 0.0
    effective_odds = odds * TAX_PL
    k = (edge / (effective_odds - 1)) * kelly_frac
    stake = bankroll * k
    stake = max(10.0, stake)
    stake = min(stake, bankroll * max_pct)
    return round(stake, 2)

def no_vig_probs(odds):
    inv = {k: 1/v for k, v in odds.items() if v}
    s = sum(inv.values())
    return {k: v/s for k, v in inv.items()}

def consensus_odds(odds_list):
    if len(odds_list) < 2: return None
    mx, mn = max(odds_list), min(odds_list)
    if (mx - mn) / mx > 0.15: return None
    return mx

# ================= MAIN RUN =================
def run():
    only_usa = "--usa-only" in sys.argv
    now = datetime.now(timezone.utc)
    bankroll = load_bankroll()
    coupons = load_json(COUPONS_FILE, [])
    
    daily_bets = sum(1 for c in coupons if parser.isoparse(c["date_time"]) > now - timedelta(days=1))
    mode_text = "NOCNY (USA)" if only_usa else "PEŁNY"
    print(f"[DEBUG] Start bota ({mode_text}). Bankroll: {bankroll} PLN.")

    for league_key, league_name in LEAGUES.items():
        if daily_bets >= MAX_BETS_PER_DAY: break
        
        # Optymalizacja nocna
        if only_usa and league_key not in USA_LEAGUES:
            continue
            
        print(f"[DEBUG] Analizuję: {league_name}...")
        for key in API_KEYS:
            try:
                r = requests.get(
                    f"https://api.the-odds-api.com/v4/sports/{league_key}/odds",
                    params={"apiKey": key, "markets": "h2h", "regions": "eu"},
                    timeout=15
                )
                
                if r.status_code != 200: continue

                events = r.json()
                for e in events:
                    dt = parser.isoparse(e["commence_time"])
                    if not (now <= dt <= now + timedelta(hours=MAX_HOURS_AHEAD)): continue

                    odds_map = defaultdict(list)
                    for bm in e["bookmakers"]:
                        for m in bm["markets"]:
                            if m["key"] != "h2h": continue
                            for o in m["outcomes"]:
                                odds_map[o["name"]].append(o["price"])

                    odds = {}
                    for name, lst in odds_map.items():
                        val = consensus_odds(lst)
                        if val and ODDS_MIN <= val <= ODDS_MAX:
                            odds[name] = val
                    
                    if len(odds) < 2: continue

                    probs = no_vig_probs(odds)
                    for sel, prob in probs.items():
                        o = odds[sel]
                        effective_odds = o * TAX_PL
                        edge = (prob - 1/effective_odds) * EDGE_MULTIPLIER.get(league_key, 1)
                        
                        is_usa = league_key in USA_LEAGUES
                        current_threshold = 0.01 if is_usa else VALUE_THRESHOLD
                        
                        if edge < current_threshold: continue
                        if any(c["home"] == e["home_team"] and c["away"] == e["away_team"] for c in coupons): continue

                        stake = calc_kelly(bankroll, o, edge, 0.5, 0.05)
                        if stake <= 1.0 or bankroll < stake: continue

                        bankroll -= stake
                        save_bankroll(bankroll)
                        possible_win = round(stake * TAX_PL * o, 2)

                        new_coupon = {
                            "league": league_key, "league_name": league_name,
                            "home": e["home_team"], "away": e["away_team"],
                            "pick": sel, "odds": o, "stake": stake,
                            "possible_win": possible_win, "status": "PENDING",
                            "date_time": dt.isoformat()
                        }
                        coupons.append(new_coupon)

                        send_msg(
                            f"⚔️ <b>VALUE BET PL (12%) • {league_name}</b>\n"
                            f"{e['home_team']} vs {e['away_team']}\n"
                            f"🎯 Typ: <b>{sel}</b>\n"
                            f"📈 Kurs: <b>{o}</b> (efekt. {round(effective_odds, 2)})\n"
                            f"💎 Edge netto: {round(edge*100,2)}%\n"
                            f"💵 Stawka: <b>{stake} PLN</b>\n"
                            f"💰 Wygrana: <b>{possible_win} PLN</b>\n"
                            f"🗓️ {dt.strftime('%m-%d %H:%M UTC')}"
                        )
                        daily_bets += 1
                        if daily_bets >= MAX_BETS_PER_DAY: break
                break 
            except: continue

    save_json(COUPONS_FILE, coupons)

if __name__ == "__main__":
    run()
