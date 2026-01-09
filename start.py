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
SOFT_KELLY_FACTOR = 0.25  # Soft Kelly fraction
MIN_ODDS = 1.5  # minimalny kurs do testów, można poluzować w trybie testowym

# ================= LIGI =================
LEAGUES = [
    "basketball_nba",                  # NBA 🏀
    "soccer_epl",                      # Premier League ⚽ PL
    "icehockey_nhl",                   # NHL 🏒
    "soccer_poland_ekstraklasa",      # Ekstraklasa ⚽ EK
    "soccer_uefa_champs_league",      # Champions League 🏆 CL
    "soccer_germany_bundesliga",       # Bundesliga 🇩🇪
    "soccer_italy_serie_a",            # Serie A 🇮🇹
    "basketball_euroleague"            # EuroLeague 🏀
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

# ================= FILE UTILS =================
def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[LOAD ERROR] {path}: {e}")
    return default

def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"[SAVE ERROR] {path}: {e}")

# ================= BANKROLL =================
def load_bankroll():
    return load_json(BANKROLL_FILE, {}).get("bankroll", START_BANKROLL)

def save_bankroll(val):
    save_json(BANKROLL_FILE, {"bankroll": round(val, 2)})

def calc_soft_kelly(bankroll, odds, edge):
    """Soft Kelly stake, dynamiczny w zależności od edge"""
    if edge <= 0 or odds <= 1:
        return 0.0
    b = odds - 1
    kelly = edge / b
    stake = bankroll * kelly * SOFT_KELLY_FACTOR
    stake = max(3.0, stake)  # minimalna stawka
    stake = min(stake, bankroll * 0.05)  # max 5% bankrolla
    return round(stake, 2)

# ================= TELEGRAM =================
def send_msg(text, target="types"):
    chat_id = T_CHAT_RESULTS if target=="results" else T_CHAT
    if not T_TOKEN or not chat_id:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True},
            timeout=10
        )
    except Exception as e:
        print(f"[TELEGRAM ERROR] {e}")

# ================= FORMAT UI =================
def format_match_time(dt):
    return dt.strftime("%d.%m.%Y • %H:%M UTC")

def format_value_card(strategy, league_key, home, away, dt, pick, odds, edge, stake):
    info = LEAGUE_INFO.get(league_key, {"name": league_key, "flag": "🎯"})
    tier = "A" if edge >= 0.08 else "B"
    return (
        f"{info['flag']} <b>{strategy.upper()} • {info['name']}</b>\n"
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
    inv = {k: 1/v for k,v in odds.items() if v}
    s = sum(inv.values())
    return {k: v/s for k,v in inv.items()}

def generate_picks(match):
    """
    Generuje typy dla Value Bet i BTTS/Over 2.5
    Zwraca listę słowników:
    [{"sel":..., "odds":..., "val":..., "strategy":...}]
    """
    picks = []
    h, a = match["home"], match["away"]
    h_o, a_o = match["odds"]["home"], match["odds"]["away"]
    d_o = match["odds"].get("draw")

    # --- VALUE BET ---
    if match["league"]=="icehockey_nhl":
        probs = no_vig_probs({"home": h_o, "away": a_o})
        p = {h: probs["home"], a: probs["away"]}
    else:
        probs = no_vig_probs({"home": h_o, "away": a_o, "draw": d_o})
        p = {h: probs["home"], a: probs["away"], "Remis": probs.get("draw",0)*0.9}

    for sel, prob in p.items():
        odds_val = h_o if sel==h else a_o if sel==a else d_o
        if odds_val and odds_val >= MIN_ODDS:
            edge = prob - (1/odds_val)
            if edge >= VALUE_THRESHOLD:
                picks.append({"sel": sel, "odds": odds_val, "val": edge, "strategy":"value"})

    # --- BTTS / Over 2.5 --- (upraszczamy testowo, kursy > MIN_ODDS)
    if h_o and a_o:
        picks.append({"sel":"BTTS", "odds": max(h_o,a_o), "val":0.02, "strategy":"btts"})
        picks.append({"sel":"Over 2.5", "odds": max(h_o,a_o), "val":0.02, "strategy":"over"})

    return picks

# ================= RESULTS =================
def check_results():
    coupons = load_json(COUPONS_FILE, [])
    bankroll = load_bankroll()
    for league in LEAGUES:
        for key in API_KEYS:
            try:
                r = requests.get(f"https://api.the-odds-api.com/v4/sports/{league}/scores",
                                 params={"apiKey": key, "daysFrom":3}, timeout=10)
                if r.status_code != 200: continue

                for c in coupons:
                    if c["status"]!="pending" or c["league"]!=league: continue

                    m = next((x for x in r.json()
                              if x["home_team"]==c["home"] and x["away_team"]==c["away"] and x.get("completed")), None)
                    if not m: continue

                    scores = {s["name"]: int(s["score"]) for s in m.get("scores",[])}
                    hs, as_ = scores.get(c["home"],0), scores.get(c["away"],0)
                    winner = c["home"] if hs>as_ else c["away"] if as_>hs else "Remis"

                    if c["strategy"]=="value":
                        win_val = round(c["stake"]*(c["odds"]-1),2) if winner==c["picked"] else 0
                    else:
                        win_val = round(c["stake"]*(c["odds"]-1),2) if winner=="BTTS" else 0

                    if win_val>0:
                        bankroll += win_val
                        c["status"]="won"
                        c["win_val"]=win_val
                        icon="✅"
                    else:
                        c["status"]="lost"
                        c["win_val"]=0
                        icon="❌"

                    send_msg(f"{icon} <b>ROZLICZENIE</b>\n{c['home']} vs {c['away']}\nTyp: {c['picked']} | Stawka: {c['stake']} PLN", target="results")
                break
            except Exception as e:
                print(f"[RESULT ERROR] {e}")
    save_bankroll(bankroll)
    save_json(COUPONS_FILE, coupons)

# ================= STATS =================
def send_stats():
    coupons = load_json(COUPONS_FILE, [])
    bankroll = load_bankroll()
    now = datetime.now(timezone.utc)

    def calc_stats(c_list):
        stats = defaultdict(lambda: {"types":0,"won":0,"lost":0})
        for c in c_list:
            stats[c["strategy"]]["types"]+=1
            stats[c["strategy"]]["won"]+=c.get("win_val",0)
            if c["status"]=="lost":
                stats[c["strategy"]]["lost"]+=c.get("stake",0)
        return stats

    def format_stats_msg(stats):
        msg=""
        for strat, data in stats.items():
            profit = data["won"]-data["lost"]
            msg+=f"📊 {strat.upper()}: {data['types']} typów | 🟢 {round(data['won'],2)} | 🔴 {round(data['lost'],2)} | 💎 {round(profit,2)}\n"
        return msg

    # --- wszystkie kupony ---
    if not coupons:
        send_msg("📊 Brak rozliczonych kuponów do analizy.", target="results")
        return

    stats = calc_stats(coupons)
    msg = format_stats_msg(stats)
    send_msg(f"📈 Statystyki | {str(now.date())}\n💰 Bankroll: {round(bankroll,2)} PLN\n\n{msg}", target="results")

# ================= RUN =================
def run():
    check_results()
    coupons = load_json(COUPONS_FILE, [])
    bankroll = load_bankroll()
    now = datetime.now(timezone.utc)
    all_picks = []

    for league in LEAGUES:
        for key in API_KEYS:
            try:
                r = requests.get(f"https://api.the-odds-api.com/v4/sports/{league}/odds",
                                 params={"apiKey":key,"markets":"h2h","regions":"eu"}, timeout=10)
                if r.status_code != 200: continue

                for e in r.json():
                    dt = parser.isoparse(e["commence_time"])
                    if not(now<=dt<=now+timedelta(hours=MAX_HOURS_AHEAD)): continue

                    odds = {}
                    for bm in e["bookmakers"]:
                        for m in bm["markets"]:
                            if m["key"]=="h2h":
                                for o in m["outcomes"]:
                                    odds[o["name"]] = max(odds.get(o["name"],0), o["price"])

                    match = {"home": e["home_team"], "away": e["away_team"], "league": league, "odds": {"home": odds.get(e["home_team"]), "away": odds.get(e["away_team"]), "draw": odds.get("Draw")}}
                    picks = generate_picks(match)

                    for pick in picks:
                        # Sprawdzenie duplikatu
                        if any(c for c in coupons if c["home"]==e["home_team"] and c["away"]==e["away_team"] and c["strategy"]==pick["strategy"] and c["sent_date"]==str(now.date())):
                            continue

                        stake = calc_soft_kelly(bankroll, pick["odds"], pick["val"])
                        if stake<=0: continue
                        bankroll -= stake
                        save_bankroll(bankroll)

                        coupons.append({
                            "home": e["home_team"],
                            "away": e["away_team"],
                            "picked": pick["sel"],
                            "odds": pick["odds"],
                            "stake": stake,
                            "league": league,
                            "strategy": pick["strategy"],
                            "status": "pending",
                            "win_val": 0,
                            "sent_date": str(now.date())
                        })

                        send_msg(format_value_card(pick["strategy"], league, e["home_team"], e["away_team"], dt, pick["sel"], pick["odds"], pick["val"], stake))
                break
            except Exception as e:
                print(f"[ODDS ERROR] {e}")

    save_json(COUPONS_FILE, coupons)

# ================= MAIN =================
if __name__=="__main__":
    if "--stats" in sys.argv:
        send_stats()
    else:
        run()