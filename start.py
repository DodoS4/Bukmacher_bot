import os
import requests
import json
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

if not API_KEYS:
    raise ValueError("❌ Brak kluczy API, dodaj ODDS_KEY… w Secrets!")

START_BANKROLL = 10000.0
BANKROLL_FILE = "bankroll.json"
COUPONS_FILE = "coupons.json"

MAX_HOURS_AHEAD = 48
MIN_EDGE = 0.0   # Debug: nie filtruj edgeu
ODDS_MIN = 1.5
ODDS_MAX = 10.0
MAX_BETS_PER_DAY = 5

LEAGUES = [
    "basketball_nba",
    "icehockey_nhl",
    "soccer_epl",
    "soccer_germany_bundesliga",
    "soccer_italy_serie_a"
]

EDGE_MULTIPLIER = {
    "basketball_nba": 0.85,
    "icehockey_nhl": 0.90,
    "soccer_epl": 0.70,
    "soccer_germany_bundesliga": 0.65,
    "soccer_italy_serie_a": 0.60
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
        json.dump(data, f, indent=2)

# ================= BANKROLL =================
def load_bankroll():
    data = load_json(BANKROLL_FILE, None)
    if not data:
        save_json(BANKROLL_FILE, {"bankroll": START_BANKROLL})
        return START_BANKROLL
    return data["bankroll"]

def save_bankroll(val):
    save_json(BANKROLL_FILE, {"bankroll": round(val, 2)})

# ================= TELEGRAM =================
def send_msg(txt, target="types"):
    chat = T_CHAT_RESULTS if target == "results" else T_CHAT
    if not T_TOKEN or not chat:
        print(f"[TELEGRAM SKIPPED]\n{txt}")
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
            json={"chat_id": chat, "text": txt, "parse_mode": "HTML"},
            timeout=10
        )
    except Exception as e:
        print(f"[TELEGRAM ERROR] {e}")

# ================= KELLY =================
def calc_kelly(bankroll, odds, edge, kelly_frac, max_pct):
    if edge <= 0 or odds <= 1:
        return 0.0
    k = (edge / (odds - 1)) * kelly_frac
    stake = bankroll * k
    stake = max(10.0, stake)
    stake = min(stake, bankroll * max_pct)
    return round(stake, 2)

# ================= VALUE =================
def no_vig_probs(odds):
    inv = {k: 1/v for k, v in odds.items() if v}
    total = sum(inv.values())
    return {k: v/total for k, v in inv.items()}

def consensus_odds(odds_list):
    if len(odds_list) < 2:
        return None
    mx, mn = max(odds_list), min(odds_list)
    if (mx - mn)/mx > 0.15:
        return None
    return round(mx, 2)

# ================= RUN =================
def run():
    now = datetime.now(timezone.utc)
    bankroll = load_bankroll()
    coupons = load_json(COUPONS_FILE, [])

    print(f"[DEBUG] Bankroll start: {bankroll} PLN")
    daily_bets = 0

    for league in LEAGUES:
        print(f"[DEBUG] Liga: {league}")
        for key in API_KEYS:
            try:
                r = requests.get(
                    f"https://api.the-odds-api.com/v4/sports/{league}/odds",
                    params={"apiKey": key, "regions":"eu","markets":"h2h"},
                    timeout=10
                )
                if r.status_code == 401:
                    print(f"[DEBUG] API 401 – zły klucz dla ligi {league} (key={key[:6]}...)")
                    continue
                if r.status_code != 200:
                    print(f"[DEBUG] API error {r.status_code} dla {league}")
                    continue

                events = r.json()
                print(f"[DEBUG] Mecze pobrane: {len(events)}")

                for e in events:
                    dt = parser.isoparse(e.get("commence_time"))
                    if not (now <= dt <= now + timedelta(hours=MAX_HOURS_AHEAD)):
                        print(f"[DEBUG] Pomijam {e['home_team']} vs {e['away_team']} – poza horyzontem")
                        continue

                    # zbieraj kursy z bukmacherów
                    odds_map = defaultdict(list)
                    for bm in e.get("bookmakers", []):
                        for mkt in bm.get("markets", []):
                            if mkt.get("key") != "h2h":
                                continue
                            for outcome in mkt.get("outcomes", []):
                                odds_map[outcome.get("name")].append(outcome.get("price"))

                    odds = {}
                    for name, lst in odds_map.items():
                        val = consensus_odds(lst)
                        print(f"[DEBUG] {name}: {lst} => consensus={val}")
                        if val and ODDS_MIN <= val <= ODDS_MAX:
                            odds[name] = val

                    if len(odds) < 2:
                        print(f"[DEBUG] Za mało kursów po consensus: {odds}")
                        continue

                    # bez vig
                    probs = no_vig_probs(odds)
                    for sel, prob in probs.items():
                        o = odds[sel]
                        edge = (prob - 1/o)*EDGE_MULTIPLIER.get(league, 1)
                        print(f"[DEBUG] Edge dla {sel}: {edge:.4f}")

                        if edge < MIN_EDGE:
                            print(f"[DEBUG] Edge < MIN_EDGE ({edge:.4f} < {MIN_EDGE}) – pomijam")
                            continue

                        # czy już mamy typ
                        exists = any(
                            c["home"] == e["home_team"] and c["away"] == e["away_team"] and c["status"] == "pending"
                            for c in coupons
                        )
                        if exists:
                            print("[DEBUG] Typ już istnieje, pomijam")
                            continue

                        stake = calc_kelly(bankroll, o, edge, 0.5, 0.05)
                        if stake <= 0 or bankroll < stake:
                            print(f"[DEBUG] Za mało bankroll na stake {stake}")
                            continue

                        bankroll -= stake
                        save_bankroll(bankroll)

                        coupon = {
                            "league": league,
                            "home": e["home_team"],
                            "away": e["away_team"],
                            "pick": sel,
                            "odds": o,
                            "stake": stake,
                            "status": "pending",
                            "date_time": e.get("commence_time")
                        }
                        coupons.append(coupon)
                        save_json(COUPONS_FILE, coupons)

                        msg = (
                            f"⚔️ <b>VALUE BET</b>\n"
                            f"{e['home_team']} vs {e['away_team']}\n"
                            f"🎯 {sel}\n"
                            f"📈 Kurs: {o}\n"
                            f"💰 Stawka: {stake:.2f} PLN"
                        )
                        send_msg(msg)
                        print(f"[DEBUG] Typ wysłany: {sel} @ {o} | {stake} PLN")

                        daily_bets += 1
                        if daily_bets >= MAX_BETS_PER_DAY:
                            print("[DEBUG] Osiągnięto limit dzienny")
                            break
                    if daily_bets >= MAX_BETS_PER_DAY:
                        break
                break
            except Exception as e:
                print(f"[DEBUG] Błąd API: {e}")
                continue

    print(f"[DEBUG] Bankroll końcowy: {bankroll} PLN")

# ================= MAIN =================
if __name__ == "__main__":
    run()