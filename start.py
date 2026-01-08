import requests
import json
import os
from datetime import datetime, timedelta, timezone

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
META_FILE = "meta.json"
START_BANKROLL = 100.0
MAX_HOURS_AHEAD = 72

MIN_ODDS = 1.5

LEAGUES = [
    "icehockey_nhl",
    "icehockey_khl",
    "basketball_nba",
    "basketball_euroliga",
    "soccer_epl",
    "soccer_england_championship",
    "soccer_poland_ekstraklasa",
    "soccer_germany_bundesliga",
    "soccer_uefa_champs_league",
    "soccer_italy_serie_a",
    "soccer_spain_la_liga",
    "soccer_italy_serie_b",
    "soccer_france_ligue_1"
]

LEAGUE_INFO = {
    "icehockey_nhl": {"name": "NHL", "flag": "🏒"},
    "icehockey_khl": {"name": "KHL", "flag": "🥅"},
    "basketball_nba": {"name": "NBA", "flag": "🏀"},
    "basketball_euroliga": {"name": "Euroliga", "flag": "🏀"},
    "soccer_epl": {"name": "Premier League", "flag": "🏴"},
    "soccer_england_championship": {"name": "Championship", "flag": "🏴"},
    "soccer_poland_ekstraklasa": {"name": "Ekstraklasa", "flag": "🇵🇱"},
    "soccer_germany_bundesliga": {"name": "Bundesliga", "flag": "🇩🇪"},
    "soccer_uefa_champs_league": {"name": "Champions League", "flag": "🏆"},
    "soccer_italy_serie_a": {"name": "Serie A", "flag": "🇮🇹"},
    "soccer_spain_la_liga": {"name": "La Liga", "flag": "🇪🇸"},
    "soccer_italy_serie_b": {"name": "Serie B", "flag": "🇮🇹"},
    "soccer_france_ligue_1": {"name": "Ligue 1", "flag": "🇫🇷"}
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
def ensure_bankroll_file():
    if not os.path.exists(BANKROLL_FILE):
        save_json(BANKROLL_FILE, {"bankroll": START_BANKROLL})

def load_bankroll():
    return load_json(BANKROLL_FILE, {}).get("bankroll", START_BANKROLL)

def save_bankroll(val):
    save_json(BANKROLL_FILE, {"bankroll": round(val, 2)})

def calc_kelly_stake(bankroll, odds, edge, kelly_frac=0.25):
    if edge <= 0 or odds <= 1:
        return 0.0
    stake = bankroll * (edge / (odds - 1)) * kelly_frac
    return round(min(max(stake, 3.0), bankroll * 0.05), 2)

# ================= TELEGRAM =================
def send_msg(text, target="types"):
    chat_id = T_CHAT_RESULTS if target == "results" else T_CHAT
    if not T_TOKEN or not chat_id:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            },
            timeout=10
        )
    except:
        pass

# ================= VALUE BET SCAN =================
def scan_offers():
    total_scanned = 0
    total_selected = 0
    coupons = []

    for league in LEAGUES:
        league_ok = False
        for key in API_KEYS:
            try:
                r = requests.get(
                    f"https://api.the-odds-api.com/v4/sports/{league}/odds",
                    params={"apiKey": key, "daysFrom": MAX_HOURS_AHEAD},
                    timeout=10
                )
                if r.status_code != 200:
                    continue
                data = r.json()
                total_scanned += len(data)
                league_ok = True

                for game in data:
                    home = game.get("home_team")
                    away = game.get("away_team")
                    if not home or not away:
                        continue

                    # Pobierz wszystkie kursy dla każdej opcji
                    outcomes_dict = {}
                    for bm in game.get("bookmakers", []):
                        for market in bm.get("markets", []):
                            for outcome in market.get("outcomes", []):
                                name = outcome.get("name")
                                price = outcome.get("price")
                                if not name or not price:
                                    continue
                                outcomes_dict.setdefault(name, []).append(price)

                    # Oblicz średni kurs (fair odds) i edge dla każdego team
                    for team, prices in outcomes_dict.items():
                        avg_odds = sum(prices)/len(prices)
                        # edge = średni kurs / 1 / (1/n) - 1 ; dla 2 outcome: fair odds 2.0
                        n_outcomes = len(outcomes_dict)
                        fair_odds = 1 / (1/n_outcomes)
                        edge = avg_odds / fair_odds - 1

                        if avg_odds < MIN_ODDS or edge <= 0:
                            continue

                        coupons.append({
                            "home": home,
                            "away": away,
                            "picked": team,
                            "odds": round(avg_odds,2),
                            "stake": 3.0,
                            "league": league,
                            "status": "pending",
                            "win_val": 0,
                            "sent_date": datetime.now(timezone.utc).date().isoformat(),
                            "edge": round(edge,3)
                        })
                        total_selected += 1
                break
            except:
                continue

        print(f"{league}: {'✅' if league_ok else '❌'}")

    save_json(COUPONS_FILE, coupons)

    # Telegram top 20 value-betów
    if total_selected > 0:
        top_bets = sorted(coupons, key=lambda x: x['edge'], reverse=True)[:20]
        msg = f"🏹 TOP VALUE BETS • {total_selected} typów\n"
        for c in top_bets:
            info = LEAGUE_INFO.get(c['league'], {"name": c['league'], "flag": "🎯"})
            msg += f"{info['flag']} {c['home']} vs {c['away']} ➤ {c['picked']} | Kurs: {c['odds']} | Edge: {c['edge']*100:.1f}%\n"
        send_msg(msg, "types")

    send_msg(f"🔍 Skanowanie ofert:\nZeskanowano: {total_scanned} meczów\nWybrano: {total_selected} value-betów", "results")

# ================= RESULTS =================
def check_results():
    coupons = load_json(COUPONS_FILE, [])
    bankroll = load_bankroll()

    for league in LEAGUES:
        for key in API_KEYS:
            try:
                r = requests.get(
                    f"https://api.the-odds-api.com/v4/sports/{league}/scores",
                    params={"apiKey": key, "daysFrom": MAX_HOURS_AHEAD},
                    timeout=10
                )
                if r.status_code != 200:
                    continue

                for c in coupons:
                    if c["status"] != "pending" or c["league"] != league:
                        continue

                    m = next((x for x in r.json()
                        if x["home_team"] == c["home"]
                        and x["away_team"] == c["away"]
                        and x.get("completed")), None)

                    if not m:
                        continue

                    scores = {s["name"]: int(s["score"]) for s in m.get("scores", [])}
                    hs, as_ = scores.get(c["home"], 0), scores.get(c["away"], 0)
                    winner = c["home"] if hs > as_ else c["away"] if as_ > hs else "Remis"

                    if winner == c["picked"]:
                        profit = round(c["stake"] * (c["odds"] - 1), 2)
                        bankroll += profit
                        c["status"] = "won"
                        c["win_val"] = profit
                    else:
                        c["status"] = "lost"
                        c["win_val"] = 0
                break
            except:
                continue

    save_bankroll(bankroll)
    save_json(COUPONS_FILE, coupons)

# ================= RUN =================
def run():
    ensure_bankroll_file()
    scan_offers()
    check_results()

if __name__ == "__main__":
    run()