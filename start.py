import requests, json, os
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

MAX_HOURS_AHEAD = 48
VALUE_THRESHOLD = 0.02
ODDS_MIN = 1.5
ODDS_MAX = 10.0
MAX_BETS_PER_DAY = 5

LEAGUES = {
    "basketball_nba": "🏀 NBA",
    "icehockey_nhl": "🏒 NHL",
    "soccer_epl": "⚽ EPL",
    "soccer_germany_bundesliga": "⚽ Bundesliga",
    "soccer_italy_serie_a": "⚽ Serie A"
}

EDGE_MULTIPLIER = {
    "basketball_nba": 0.85,
    "icehockey_nhl": 0.90,
    "soccer_epl": 0.70,
    "soccer_germany_bundesliga": 0.65,
    "soccer_italy_serie_a": 0.60
}

# ================= UTILS =================
def load_json(path, default):
    """Wczytaj JSON i wymuś typ zgodny z default (lista/dict)"""
    if os.path.exists(path):
        try:
            data = json.load(open(path, "r", encoding="utf-8"))
            # Jeśli default to lista, a data to dict, zamień na listę wartości
            if isinstance(default, list) and isinstance(data, dict):
                return list(data.values())
            return data
        except:
            pass
    return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def load_bankroll():
    data = load_json(BANKROLL_FILE, None)
    if not data:
        save_json(BANKROLL_FILE, {"bankroll": START_BANKROLL})
        return START_BANKROLL
    return data["bankroll"]

def save_bankroll(val):
    save_json(BANKROLL_FILE, {"bankroll": round(val, 2)})

def send_msg(txt, target="types"):
    chat = T_CHAT_RESULTS if target == "results" else T_CHAT
    if not T_TOKEN or not chat:
        print("[DEBUG] Telegram skipped:\n", txt)
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
            json={"chat_id": chat, "text": txt, "parse_mode": "HTML"},
            timeout=10
        )
    except Exception as e:
        print(f"[DEBUG] Telegram error: {e}")

def calc_kelly(bankroll, odds, edge, kelly_frac, max_pct):
    if edge <= 0 or odds <= 1: return 0.0
    k = (edge / (odds - 1)) * kelly_frac
    stake = bankroll * k
    stake = max(10.0, stake)
    stake = min(stake, bankroll * max_pct)
    return round(stake, 2)

def no_vig_probs(odds):
    inv = {k: 1 / v for k, v in odds.items() if v}
    s = sum(inv.values())
    return {k: v / s for k, v in inv.items()}

def consensus_odds(odds_list):
    if len(odds_list) < 2: return None
    mx, mn = max(odds_list), min(odds_list)
    if (mx - mn) / mx > 0.15: return None
    return mx

# ================= MAIN RUN =================
def run():
    now = datetime.now(timezone.utc)
    bankroll = load_bankroll()
    coupons = load_json(COUPONS_FILE, [])
    if not isinstance(coupons, list):
        coupons = list(coupons)  # Bezpiecznie zamień na listę
    daily_bets = 0

    for league_key, league_name in LEAGUES.items():
        for key in API_KEYS:
            try:
                r = requests.get(
                    f"https://api.the-odds-api.com/v4/sports/{league_key}/odds",
                    params={"apiKey": key, "markets": "h2h", "regions": "eu"},
                    timeout=10
                )
                if r.status_code != 200: continue

                for e in r.json():
                    dt = parser.isoparse(e["commence_time"])
                    if not (now <= dt <= now + timedelta(hours=MAX_HOURS_AHEAD)):
                        continue

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
                        edge = (prob - 1 / o) * EDGE_MULTIPLIER.get(league_key, 1)
                        if edge < VALUE_THRESHOLD: continue

                        if any(c["home"] == e["home_team"] and c["away"] == e["away_team"] and c["status"] == "pending" for c in coupons):
                            continue

                        stake = calc_kelly(bankroll, o, edge, 0.5, 0.05)
                        if stake <= 0 or bankroll < stake: continue

                        bankroll -= stake
                        save_bankroll(bankroll)

                        coupons.append({
                            "league": league_key,
                            "league_name": league_name,
                            "home": e["home_team"],
                            "away": e["away_team"],
                            "pick": sel,
                            "odds": o,
                            "stake": stake,
                            "status": "pending",
                            "date_time": dt.isoformat()
                        })

                        send_msg(
                            f"⚔️ VALUE BET • {league_name}\n"
                            f"{e['home_team']} vs {e['away_team']}\n"
                            f"🎯 {sel}\n"
                            f"📈 {o}\n"
                            f"💎 Edge: {round(edge*100,2)}%\n"
                            f"💰 Stawka: {stake} PLN\n"
                            f"🗓️ Data i godzina: {dt.strftime('%Y-%m-%d %H:%M UTC')}"
                        )

                        daily_bets += 1
                        if daily_bets >= MAX_BETS_PER_DAY: break
                    if daily_bets >= MAX_BETS_PER_DAY: break
                break
            except Exception as e:
                print(f"[DEBUG] API error: {e}")
                continue

    save_json(COUPONS_FILE, coupons)
    print(f"[DEBUG] Bankroll końcowy: {bankroll:.2f} PLN")


if __name__ == "__main__":
    run()