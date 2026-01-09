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
START_BANKROLL = 500.0

MAX_HOURS_AHEAD = 48 
VALUE_THRESHOLD = 0.035
KELLY_FRACTION = 0.25

# ================= LIGI =================
LEAGUES = [
    "basketball_nba",
    "soccer_epl",
    "icehockey_nhl",
    "soccer_poland_ekstraklasa",
    "soccer_uefa_champs_league"
]

LEAGUE_INFO = {
    "basketball_nba": {"name": "NBA", "flag": "🏀"},
    "soccer_epl": {"name": "Premier League", "flag": "⚽ PL"},
    "icehockey_nhl": {"name": "NHL", "flag": "🏒"},
    "soccer_poland_ekstraklasa": {"name": "Ekstraklasa", "flag": "⚽ EK"},
    "soccer_uefa_champs_league": {"name": "Champions League", "flag": "🏆 CL"}
}

MIN_ODDS = {
    "basketball_nba": 1.8,
    "icehockey_nhl": 2.3,
    "soccer_epl": 2.5,
    "soccer_poland_ekstraklasa": 2.5,
    "soccer_uefa_champs_league": 2.5
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
    data = load_json(BANKROLL_FILE, None)
    if not data or "bankroll" not in data:
        bankroll = START_BANKROLL
        save_bankroll(bankroll)
        return bankroll
    return data.get("bankroll", START_BANKROLL)

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

# ================= FORMAT UI =================
def format_match_time(dt):
    return dt.strftime("%d.%m.%Y • %H:%M UTC")

def format_value_card(league_key, home, away, dt, pick, odds, edge, stake):
    info = LEAGUE_INFO.get(league_key, {"name": league_key, "flag": "🎯"})
    tier = "A" if edge >= 0.08 else "B"
    return (
        f"{info['flag']} <b>VALUE BET • {info['name']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"<b>{home} vs {away}</b>\n"
        f"🕒 {format_match_time(dt)}\n"
        f"🎯 Typ: <b>{pick}</b>\n"
        f"📈 Kurs: <b>{odds}</b>\n"
        f"💎 Edge: <b>+{round(edge*100,2)}%</b>\n"
        f"🏷 Tier: <b>{tier}</b>\n"
        f"💰 Stawka: <b>{stake} PLN</b>"
    )

# ================= ODDS =================
def no_vig_probs(odds):
    inv = {k: 1/v for k, v in odds.items() if v}
    s = sum(inv.values())
    return {k: v/s for k, v in inv.items()}

def generate_pick(match):
    h_o = match["odds"]["home"]
    a_o = match["odds"]["away"]
    d_o = match["odds"].get("draw")

    if not h_o or not a_o: return None

    if match["league"] == "icehockey_nhl":
        probs = no_vig_probs({"home": h_o, "away": a_o})
        p = {match["home"]: probs["home"], match["away"]: probs["away"]}
    else:
        probs = no_vig_probs({"home": h_o, "away": a_o, "draw": d_o}) if d_o else no_vig_probs({"home": h_o, "away": a_o})
        p = {match["home"]: probs["home"], match["away"]: probs["away"]}
        if d_o: p["Remis"] = probs.get("draw", 0) * 0.9

    min_odds = MIN_ODDS.get(match["league"], 2.5)
    best = None
    for sel, prob in p.items():
        odds = h_o if sel==match["home"] else a_o if sel==match["away"] else d_o
        if odds and odds >= min_odds:
            edge = prob - (1/odds)
            if edge >= VALUE_THRESHOLD:
                if not best or edge > best["val"]:
                    best = {"sel": sel, "odds": odds, "val": edge}
    return best

# ================= RESULTS =================
def check_results():
    coupons = load_json(COUPONS_FILE, [])
    bankroll = load_bankroll()
    for league in LEAGUES:
        for key in API_KEYS:
            try:
                r = requests.get(
                    f"https://api.the-odds-api.com/v4/sports/{league}/scores",
                    params={"apiKey": key, "daysFrom": 3},
                    timeout=10
                )
                if r.status_code != 200: continue

                for c in coupons:
                    if c["status"]!="pending" or c["league"]!=league: continue

                    m = next((x for x in r.json()
                              if x["home_team"]==c["home"]
                              and x["away_team"]==c["away"]
                              and x.get("completed")), None)
                    if not m: continue

                    scores = {s["name"]: int(s["score"]) for s in m.get("scores",[])}
                    hs, as_ = scores.get(c["home"],0), scores.get(c["away"],0)
                    
                    if hs > as_: winner = c["home"]
                    elif as_ > hs: winner = c["away"]
                    else: winner = "Remis"

                    if winner == c["picked"]:
                        profit = round(c["stake"] * (c["odds"] - 1), 2)
                        bankroll += (c["stake"] + profit)
                        c["status"] = "won"
                        c["win_val"] = profit
                        icon = "✅"
                    else:
                        c["status"] = "lost"
                        c["win_val"] = 0
                        icon = "❌"

                    send_msg(f"{icon} <b>ROZLICZENIE</b>\n{c['home']} vs {c['away']}\nTyp: {c['picked']} | Wynik: {hs}:{as_}\nStawka: {c['stake']} PLN", target="results")
                break
            except: continue
    save_bankroll(bankroll)
    save_json(COUPONS_FILE, coupons)

# ================= RUN =================
def run():
    check_results()
    coupons = load_json(COUPONS_FILE, [])
    bankroll = load_bankroll()
    now = datetime.now(timezone.utc)
    all_picks = []

    # DEDUPLIKACJA: Tworzymy zbiór kluczy dla zakładów, które już są w pliku
    existing_bets = {f"{c['home']}|{c['away']}|{c['picked']}" for c in coupons if c['status'] == 'pending'}

    for league in LEAGUES:
        for key in API_KEYS:
            try:
                r = requests.get(
                    f"https://api.the-odds-api.com/v4/sports/{league}/odds",
                    params={"apiKey": key, "markets":"h2h","regions":"eu"},
                    timeout=10
                )
                if r.status_code != 200: continue

                for e in r.json():
                    dt = parser.isoparse(e["commence_time"])
                    if not(now <= dt <= now + timedelta(hours=MAX_HOURS_AHEAD)): continue

                    odds = {}
                    for bm in e["bookmakers"]:
                        for m in bm["markets"]:
                            if m["key"]=="h2h":
                                for o in m["outcomes"]:
                                    odds[o["name"]] = max(odds.get(o["name"],0), o["price"])

                    pick = generate_pick({
                        "home": e["home_team"],
                        "away": e["away_team"],
                        "league": league,
                        "odds": {"home": odds.get(e["home_team"]),
                                 "away": odds.get(e["away_team"]),
                                 "draw": odds.get("Draw")}
                    })

                    if pick:
                        # Sprawdzamy, czy ten zakład już istnieje
                        bet_key = f"{e['home_team']}|{e['away_team']}|{pick['sel']}"
                        if bet_key not in existing_bets:
                            all_picks.append((pick, e, dt, league))
                            existing_bets.add(bet_key) # Blokujemy duplikaty w ramach tej samej sesji
                break
            except: continue

    # Dodawanie nowych kuponów
    for pick, e, dt, league in sorted(all_picks, key=lambda x: x[0]["val"], reverse=True):
        stake = calc_kelly_stake(bankroll, pick["odds"], pick["val"])
        if stake <= 0 or stake > bankroll: continue

        bankroll -= stake
        
        coupons.append({
            "home": e["home_team"],
            "away": e["away_team"],
            "picked": pick["sel"],
            "odds": pick["odds"],
            "stake": stake,
            "league": league,
            "status": "pending",
            "win_val": 0,
            "sent_date": str(now.date()),
            "type": "value"
        })

        send_msg(format_value_card(league, e["home_team"], e["away_team"], dt, pick["sel"], pick["odds"], pick["val"], stake))

    save_bankroll(bankroll)
    save_json(COUPONS_FILE, coupons)

# ================= STATS =================
def send_stats():
    coupons = load_json(COUPONS_FILE, [])
    bankroll = load_bankroll()
    now = datetime.now(timezone.utc)

    value_coupons = [c for c in coupons if c.get("type")=="value"]
    if not value_coupons:
        send_msg("📊 Brak danych do statystyk.", target="results")
        return

    stats = defaultdict(lambda: {"types":0,"won_val":0,"lost_val":0})
    for c in value_coupons:
        if c["status"] == "pending": continue
        stats[c["league"]]["types"] += 1
        if c["status"] == "won":
            stats[c["league"]]["won_val"] += c.get("win_val",0)
        else:
            stats[c["league"]]["lost_val"] += c.get("stake",0)

    msg = ""
    for league, data in stats.items():
        profit = data["won_val"] - data["lost_val"]
        info = LEAGUE_INFO.get(league, {"name": league, "flag": "🎯"})
        msg += f"{info['flag']} {info['name']}: Typów {data['types']} | Zysk: {round(profit,2)} PLN\n"

    send_msg(f"📊 <b>STATYSTYKI DNIA</b>\n{str(now.date())}\n💰 Bankroll: {round(bankroll,2)} PLN\n\n{msg}", target="results")

if __name__=="__main__":
    if "--stats" in sys.argv:
        send_stats()
    else:
        run()
