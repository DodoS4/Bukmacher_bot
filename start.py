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
    os.getenv("ODDS_KEY_3")
]
API_KEYS = [k for k in KEYS_POOL if k]

COUPONS_FILE = "coupons.json"
BANKROLL_FILE = "bankroll.json"
START_BANKROLL = 100.0

MAX_HOURS_AHEAD = 48
MAX_PICKS_PER_DAY = 5

VALUE_THRESHOLD = 0.07
CORE_EDGE = 0.09
SUPPORT_EDGE = 0.05

MIN_ODDS_SOCCER = 2.50
MIN_ODDS_NHL = 2.30

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

DYNAMIC_FORMS = {}
LAST_MATCH_TIME = {}

# ================= CZAS =================
def format_match_time(dt_utc):
    return dt_utc.strftime("%d.%m.%Y • %H:%M UTC")

# ================= BANKROLL =================
def load_bankroll():
    if os.path.exists(BANKROLL_FILE):
        try:
            with open(BANKROLL_FILE, "r") as f:
                return float(json.load(f).get("bankroll", START_BANKROLL))
        except:
            return START_BANKROLL
    return START_BANKROLL

def save_bankroll(val):
    with open(BANKROLL_FILE, "w") as f:
        json.dump({"bankroll": round(val, 2)}, f)

def calc_kelly_stake(bankroll, odds, edge, kelly_frac=0.25):
    if edge <= 0 or odds <= 1:
        return 0.0
    stake = bankroll * kelly_frac * (edge / odds)
    stake = max(3.0, stake)
    stake = min(stake, bankroll * 0.05)
    return round(stake, 2)

# ================= TELEGRAM =================
def send_msg(text, target="types"):
    chat_id = T_CHAT_RESULTS if target == "results" else T_CHAT
    if not T_TOKEN or not chat_id:
        return
    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        requests.post(url, json=payload, timeout=15)
    except:
        pass

# ================= DANE =================
def load_coupons():
    if os.path.exists(COUPONS_FILE):
        try:
            with open(COUPONS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []
    return []

def save_coupons(coupons):
    with open(COUPONS_FILE, "w", encoding="utf-8") as f:
        json.dump(coupons[-2000:], f, indent=4)

# ================= FORMY =================
def fetch_real_team_forms():
    new_forms, last_times = {}, {}
    for league in LEAGUES:
        for api_key in API_KEYS:
            try:
                r = requests.get(
                    f"https://api.the-odds-api.com/v4/sports/{league}/scores",
                    params={"apiKey": api_key, "daysFrom": 14},
                    timeout=15
                )
                if r.status_code != 200:
                    continue

                for match in r.json():
                    h, a = match["home_team"], match["away_team"]
                    m_time = parser.isoparse(match["commence_time"])
                    last_times[h] = max(last_times.get(h, m_time), m_time)
                    last_times[a] = max(last_times.get(a, m_time), m_time)

                    if not match.get("completed"):
                        continue

                    scores = {s["name"]: int(s["score"]) for s in match.get("scores", [])}
                    hs, as_ = scores.get(h, 0), scores.get(a, 0)

                    new_forms.setdefault(h, [])
                    new_forms.setdefault(a, [])

                    if hs > as_:
                        new_forms[h].append(1)
                        new_forms[a].append(0)
                    elif as_ > hs:
                        new_forms[h].append(0)
                        new_forms[a].append(1)
                    else:
                        new_forms[h].append(0.5)
                        new_forms[a].append(0.5)
                break
            except:
                continue
    return new_forms, last_times

def get_team_form(team):
    res = DYNAMIC_FORMS.get(team, [])
    if not res:
        return 0.5
    weights = [1, 1.1, 1.2, 1.3, 1.4][-len(res):]
    return sum(r * w for r, w in zip(res, weights)) / sum(weights)

# ================= BEST ODDS SAFE =================
def get_best_odds_safe(event):
    best = {}
    try:
        for bm in event.get("bookmakers", []):
            for m in bm.get("markets", []):
                if m["key"] != "h2h":
                    continue
                for o in m["outcomes"]:
                    name = o["name"]
                    price = o["price"]
                    if name not in best or price > best[name]:
                        best[name] = price
    except:
        best = {}

    if len(best) < 2:
        try:
            odds = event["bookmakers"][0]["markets"][0]["outcomes"]
            best = {o["name"]: o["price"] for o in odds}
        except:
            return None

    return best

# ================= VALUE =================
def generate_pick(match):
    h_o, a_o, d_o = match["odds"]["home"], match["odds"]["away"], match["odds"].get("draw")
    if not h_o or not a_o:
        return None

    curr_min = MIN_ODDS_NHL if match["league"] == "icehockey_nhl" else MIN_ODDS_SOCCER
    if match["league"] == "icehockey_nhl":
        d_o = None

    raw_sum = (1/h_o + 1/a_o + (1/d_o if d_o else 0))
    p_h, p_a = (1/h_o)/raw_sum, (1/a_o)/raw_sum
    p_d = ((1/d_o)/raw_sum) if d_o else 0

    f_h, f_a = get_team_form(match["home"]), get_team_form(match["away"])

    final_h = 0.2 * f_h + 0.8 * p_h
    final_a = 0.2 * f_a + 0.8 * p_a
    final_d = p_d * 0.92 if d_o else 0

    opts = []
    if h_o >= curr_min:
        opts.append({"sel": match["home"], "odds": h_o, "val": final_h - (1/h_o)})
    if a_o >= curr_min:
        opts.append({"sel": match["away"], "odds": a_o, "val": final_a - (1/a_o)})
    if d_o and d_o >= MIN_ODDS_SOCCER:
        opts.append({"sel": "Remis", "odds": d_o, "val": final_d - (1/d_o)})

    if not opts:
        return None

    best = max(opts, key=lambda x: x["val"])
    return best if best["val"] >= VALUE_THRESHOLD else None

# ================= ROZLICZENIA =================
def check_results():
    coupons = load_coupons()
    bankroll = load_bankroll()

    for league in LEAGUES:
        for api_key in API_KEYS:
            try:
                r = requests.get(
                    f"https://api.the-odds-api.com/v4/sports/{league}/scores",
                    params={"apiKey": api_key, "daysFrom": 3},
                    timeout=15
                )
                if r.status_code != 200:
                    continue

                for c in coupons:
                    if c["status"] != "pending" or c["league"] != league:
                        continue

                    match = next(
                        (m for m in r.json()
                         if m["home_team"] == c["home"]
                         and m["away_team"] == c["away"]
                         and m.get("completed")),
                        None
                    )
                    if not match:
                        continue

                    scores = {s["name"]: int(s["score"]) for s in match.get("scores", [])}
                    hs, as_ = scores.get(c["home"], 0), scores.get(c["away"], 0)
                    winner = c["home"] if hs > as_ else c["away"] if as_ > hs else "Remis"

                    if c["picked"] == winner:
                        c["status"] = "won"
                        c["win_val"] = round(c["odds"] * c["stake"], 2)
                        bankroll += c["win_val"] - c["stake"]
                        icon = "✅"
                    else:
                        c["status"] = "lost"
                        c["win_val"] = 0
                        bankroll -= c["stake"]
                        icon = "❌"

                    send_msg(
                        f"{icon} <b>ROZLICZENIE MECZU</b>\n"
                        f"{c['home']} vs {c['away']}\n"
                        f"Typ: {c['picked']}\n"
                        f"Stawka: {c['stake']} PLN",
                        "results"
                    )
                break
            except:
                continue

    save_bankroll(bankroll)
    save_coupons(coupons)

# ================= RUN =================
def run():
    global DYNAMIC_FORMS, LAST_MATCH_TIME

    check_results()
    DYNAMIC_FORMS, LAST_MATCH_TIME = fetch_real_team_forms()

    coupons = load_coupons()
    bankroll = load_bankroll()
    now_utc = datetime.now(timezone.utc)
    today = now_utc.date()

    sent_today = [c for c in coupons if c.get("sent_date") == str(today)]
    if len(sent_today) >= MAX_PICKS_PER_DAY:
        return

    all_picks = []

    for league in LEAGUES:
        for api_key in API_KEYS:
            try:
                r = requests.get(
                    f"https://api.the-odds-api.com/v4/sports/{league}/odds",
                    params={"apiKey": api_key, "regions": "eu,uk,us", "markets": "h2h"},
                    timeout=15
                )
                if r.status_code != 200:
                    continue

                for event in r.json():
                    m_dt = parser.isoparse(event["commence_time"])
                    if not (now_utc <= m_dt <= now_utc + timedelta(hours=MAX_HOURS_AHEAD)):
                        continue

                    if any(c["home"] == event["home_team"] and c["away"] == event["away_team"] for c in coupons):
                        continue

                    best_odds = get_best_odds_safe(event)
                    if not best_odds:
                        continue

                    h_o = best_odds.get(event["home_team"])
                    a_o = best_odds.get(event["away_team"])
                    d_o = best_odds.get("Draw")

                    pick = generate_pick({
                        "home": event["home_team"],
                        "away": event["away_team"],
                        "league": league,
                        "odds": {"home": h_o, "away": a_o, "draw": d_o},
                        "commence_time": event["commence_time"]
                    })

                    if pick:
                        pick.update({"m": event, "league": league, "m_dt": m_dt})
                        all_picks.append(pick)
                break
            except:
                continue

    for p in sorted(all_picks, key=lambda x: x["val"], reverse=True):
        if len(sent_today) >= MAX_PICKS_PER_DAY:
            break

        if p["val"] >= CORE_EDGE:
            stake = calc_kelly_stake(bankroll, p["odds"], p["val"], kelly_frac=0.25)
        else:
            stake = calc_kelly_stake(bankroll, p["odds"], p["val"], kelly_frac=0.12)

        if stake <= 0:
            continue

        m = p["m"]
        info = LEAGUE_INFO.get(p["league"], {"name": p["league"], "flag": "⚽"})
        match_time = format_match_time(p["m_dt"])
        edge_pct = round(p["val"] * 100, 2)

        send_msg(
            f"{info['flag']} <b>VALUE BET</b> • {info['name']}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"{m['home_team']} vs {m['away_team']}\n"
            f"🕒 {match_time}\n\n"
            f"🎯 Typ: <b>{p['sel']}</b>\n"
            f"📈 Kurs: <b>{p['odds']}</b>\n"
            f"💎 Edge: <b>+{edge_pct}%</b>\n"
            f"💰 Stawka: <b>{stake} PLN</b>"
        )

        coupons.append({
            "home": m["home_team"],
            "away": m["away_team"],
            "picked": p["sel"],
            "odds": p["odds"],
            "stake": stake,
            "status": "pending",
            "date": m["commence_time"],
            "league": p["league"],
            "win_val": 0,
            "sent_date": str(today)
        })

        sent_today.append(True)
        # ⚡ zapisz bankroll przy każdym dodaniu typów
        save_bankroll(bankroll)

    save_coupons(coupons)

    send_msg(
        f"💼 <b>STATUS BANKROLLA</b>\n"
        f"━━━━━━━━━━━━━━\n"
        f"Bankroll: <b>{round(load_bankroll(),2)} PLN</b>\n"
        f"Typy dziś: <b>{len(sent_today)}</b> / {MAX_PICKS_PER_DAY}",
        target="results"
    )

if __name__ == "__main__":
    run()