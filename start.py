import requests
import json
import os
import logging
from datetime import datetime, timezone

# ================= CONFIG =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS")

# Obsługa wielu kluczy API
API_KEYS = [k for k in [
    os.getenv("ODDS_KEY"),
    os.getenv("ODDS_KEY_2"),
    os.getenv("ODDS_KEY_3")
] if k]

COUPONS_FILE = "coupons.json"
BANKROLL_FILE = "bankroll.json"
META_FILE = "meta.json"
START_BANKROLL = 100.0

# Parametry strategii
VALUE_THRESHOLD = 0.035  # Przewaga 3.5%
MAX_HOURS_AHEAD = 24

LEAGUES = [
    "icehockey_nhl",
    "basketball_nba",
    "soccer_epl",
    "soccer_england_championship",
    "soccer_poland_ekstraklasa",
    "soccer_germany_bundesliga",
    "soccer_uefa_champs_league"
]

LEAGUE_INFO = {
    "icehockey_nhl": {"name": "NHL", "flag": "🏒"},
    "basketball_nba": {"name": "NBA", "flag": "🏀"},
    "soccer_epl": {"name": "Premier League", "flag": "🏴"},
    "soccer_england_championship": {"name": "Championship", "flag": "🏴"},
    "soccer_poland_ekstraklasa": {"name": "Ekstraklasa", "flag": "🇵🇱"},
    "soccer_germany_bundesliga": {"name": "Bundesliga", "flag": "🇩🇪"},
    "soccer_uefa_champs_league": {"name": "Champions League", "flag": "🏆"}
}

# Logowanie błędów
logging.basicConfig(filename='bot_errors.log', level=logging.ERROR, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

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
        json.dump(data, f, indent=4)

def load_bankroll():
    return load_json(BANKROLL_FILE, {}).get("bankroll", START_BANKROLL)

def save_bankroll(val):
    save_json(BANKROLL_FILE, {"bankroll": round(val, 2)})

def send_msg(text, target="types"):
    chat_id = T_CHAT_RESULTS if target == "results" else T_CHAT
    if not T_TOKEN or not chat_id: return
    try:
        requests.post(f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}, timeout=10)
    except Exception as e: logging.error(f"Telegram Error: {e}")

# ================= KELLY & VALUE =================
def calc_kelly_stake(bankroll, odds, edge, kelly_frac=0.25):
    if edge <= 0 or odds <= 1: return 0.0
    # Proporcjonalne skalowanie stawki do kapitału
    stake = bankroll * (edge / (odds - 1)) * kelly_frac
    # Min 2 PLN, Max 5% bankrolla
    return round(min(max(stake, 2.0), bankroll * 0.05), 2)

def find_value_bets():
    coupons = load_json(COUPONS_FILE, [])
    bankroll = load_bankroll()
    
    for league in LEAGUES:
        for key in API_KEYS:
            try:
                r = requests.get(f"https://api.the-odds-api.com/v4/sports/{league}/odds",
                                 params={"apiKey": key, "regions": "eu", "markets": "h2h"}, timeout=15)
                if r.status_code == 429: continue #
                if r.status_code != 200: break
                
                events = r.json()
                for ev in events:
                    home, away = ev["home_team"], ev["away_team"]
                    outcomes = {"home": [], "away": [], "draw": []}
                    
                    for bookie in ev.get("bookmakers", []):
                        for mkt in bookie.get("markets", []):
                            if mkt["key"] == "h2h":
                                for o in mkt["outcomes"]:
                                    if o["name"] == home: outcomes["home"].append(o["price"])
                                    elif o["name"] == away: outcomes["away"].append(o["price"])
                                    else: outcomes["draw"].append(o["price"])

                    for side in ["home", "away", "draw"]:
                        prices = outcomes[side]
                        if len(prices) < 3: continue
                        
                        best_odds, avg_odds = max(prices), sum(prices)/len(prices)
                        edge = (best_odds / avg_odds) - 1

                        if edge > VALUE_THRESHOLD:
                            pick_name = home if side=="home" else away if side=="away" else "Remis"
                            if not any(c for c in coupons if c["home"] == home and c["picked"] == pick_name):
                                stake = calc_kelly_stake(bankroll, best_odds, edge)
                                if stake >= 2.0:
                                    new_bet = {
                                        "home": home, "away": away, "picked": pick_name,
                                        "odds": best_odds, "stake": stake, "edge": round(edge, 4),
                                        "league": league, "status": "pending",
                                        "sent_date": datetime.now(timezone.utc).date().isoformat()
                                    }
                                    coupons.append(new_bet)
                                    # Automatyczne odjęcie stawki od kapitału
                                    bankroll -= stake 
                                    send_msg(f"✅ <b>NOWA OKAZJA</b>\n{home} - {away}\nTyp: {pick_name} @ {best_odds}\nStawka: {stake} PLN")
                break
            except Exception as e: logging.error(f"ValueFinder Error ({league}): {e}"); continue

    save_bankroll(bankroll)
    save_json(COUPONS_FILE, coupons)

# ================= RESULTS & STATS =================
def check_results():
    coupons = load_json(COUPONS_FILE, [])
    bankroll = load_bankroll()
    
    for league in LEAGUES:
        for key in API_KEYS:
            try:
                r = requests.get(f"https://api.the-odds-api.com/v4/sports/{league}/scores",
                                 params={"apiKey": key, "daysFrom": 3}, timeout=10)
                if r.status_code != 200: continue
                
                for c in coupons:
                    if c["status"] != "pending" or c["league"] != league: continue
                    m = next((x for x in r.json() if x["home_team"] == c["home"] and x["away_team"] == c["away"] and x.get("completed")), None)
                    if not m: continue

                    scores = {s["name"]: int(s["score"]) for s in m.get("scores", [])}
                    hs, as_ = scores.get(c["home"], 0), scores.get(c["away"], 0)
                    winner = c["home"] if hs > as_ else c["away"] if as_ > hs else "Remis"

                    if winner == c["picked"]:
                        profit = round(c["stake"] * (c["odds"] - 1), 2)
                        bankroll += (c["stake"] + profit) # Zwrot stawki + zysk
                        c["status"] = "won"; c["win_val"] = profit
                    else:
                        c["status"] = "lost"; c["win_val"] = 0
                break
            except: continue
    save_bankroll(bankroll)
    save_json(COUPONS_FILE, coupons)

def league_stats(coupons, start, end):
    stats = {}
    for c in coupons:
        lg = c["league"]
        if lg not in stats: stats[lg] = {"stake": 0, "profit": 0, "cnt": 0, "pending": 0}
        if c["status"] == "pending": stats[lg]["pending"] += 1; continue
        if start <= c.get("sent_date", "") <= end:
            stats[lg]["stake"] += c["stake"]
            stats[lg]["profit"] += c["win_val"] if c["status"] == "won" else -c["stake"]
            stats[lg]["cnt"] += 1
    return stats

def send_summary(stats, title):
    if not stats: return
    total_profit = sum(s["profit"] for s in stats.values())
    total_stake = sum(s["stake"] for s in stats.values())
    roi = (total_profit / total_stake * 100) if total_stake > 0 else 0
    
    msg = f"{title}\n━━━━━━━━━━━━━━━━━━\n"
    msg += f"💰 <b>Zysk: {round(total_profit, 2)} PLN</b> | ROI: {round(roi, 1)}%\n"
    msg += f"🏦 <b>Bankroll: {load_bankroll()} PLN</b>\n━━━━━━━━━━━━━━━━━━\n"
    
    for lg, s in sorted(stats.items(), key=lambda x: (x[1]['cnt'] == 0, x[1]['profit']), reverse=True):
        info = LEAGUE_INFO.get(lg, {"name": lg, "flag": "🎯"})
        if s["cnt"] > 0: msg += f"{info['flag']} {info['name']}: <b>{round(s['profit'],2)} PLN</b> ({s['cnt']})\n"
        if s["pending"] > 0: msg += f"⏳ {info['name']}: {s['pending']} pending\n"
        elif s["cnt"] == 0: msg += f"⚪ {info['name']}: Brak gier\n"
    send_msg(msg, "results")

# ================= RUN =================
def run():
    check_results()
    find_value_bets()
    
    coupons = load_json(COUPONS_FILE, [])
    meta = load_json(META_FILE, {})
    today = datetime.now(timezone.utc).date().isoformat()

    if meta.get("last_daily") != today:
        stats = league_stats(coupons, today, today)
        send_summary(stats, f"📊 <b>PODSUMOWANIE DZIENNE • {today}</b>")
        meta["last_daily"] = today
    save_json(META_FILE, meta)

if __name__ == "__main__":
    run()
