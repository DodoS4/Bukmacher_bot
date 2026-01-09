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

def format_value_card(match):
    info = LEAGUE_INFO.get(match["league"], {"name": match["league"], "flag": "🎯"})
    tier = "A" if match.get("val",0) >= 0.08 else "B"
    return (
        f"{info['flag']} <b>VALUE BET • {info['name']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"<b>{match['home']} vs {match['away']}</b>\n"
        f"🕒 {format_match_time(match['dt'])}\n"
        f"🎯 Typ: <b>{match['sel']}</b>\n"
        f"📈 Kurs: <b>{match['odds']}</b>\n"
        f"💎 Edge: <b>+{round(match.get('val',0)*100,2)}%</b>\n"
        f"🏷 Tier: <b>{tier}</b>\n"
        f"💰 Stawka: <b>{match['stake']} PLN</b>"
    )

def format_btts_over_card(match):
    info = LEAGUE_INFO.get(match["league"], {"name": match["league"], "flag": "🎯"})
    msg = f"{info['flag']} <b>BTTS / OVER • {info['name']}</b>\n━━━━━━━━━━━━━━━━━━\n"
    msg += f"<b>{match['home']} vs {match['away']}</b>\n🕒 {format_match_time(match['dt'])}\n"
    for t in match["types"]:
        msg += f"🎯 Typ: <b>{t['type']}</b>\n📈 Kurs: <b>{t['odds']}</b>\n💎 Edge: <b>+{round(t['val']*100,2)}%</b>\n🏷 Tier: <b>{t['tier']}</b>\n💰 Stawka: <b>{t['stake']} PLN</b>\n\n"
    return msg

# ================= ODDS =================
def no_vig_probs(odds):
    inv = {k: 1/v for k, v in odds.items() if v}
    s = sum(inv.values())
    return {k: v/s for k, v in inv.items()}

def generate_value_pick(match):
    h_o = match["odds"]["home"]
    a_o = match["odds"]["away"]
    d_o = match["odds"].get("draw")
    min_odds = MIN_ODDS.get(match["league"], 2.5)

    if match["league"] == "icehockey_nhl":
        probs = no_vig_probs({"home": h_o, "away": a_o})
        p = {match["home"]: probs["home"], match["away"]: probs["away"]}
    else:
        probs = no_vig_probs({"home": h_o, "away": a_o, "draw": d_o})
        p = {match["home"]: probs["home"], match["away"]: probs["away"], "Remis": probs.get("draw",0)*0.9}

    best = None
    for sel, prob in p.items():
        odds = h_o if sel==match["home"] else a_o if sel==match["away"] else d_o
        if odds and odds >= min_odds:
            edge = prob - (1/odds)
            if edge >= VALUE_THRESHOLD:
                if not best or edge > best.get("val",0):
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
    coupons = load_json(COUPONS_FILE, [])
    bankroll = load_bankroll()
    now = datetime.now(timezone.utc)

    value_picks = []
    btts_over_picks = []

    for league in LEAGUES:
        for key in API_KEYS:
            try:
                r = requests.get(
                    f"https://api.the-odds-api.com/v4/sports/{league}/odds",
                    params={"apiKey": key, "markets":"h2h,totals","regions":"eu"},
                    timeout=10
                )
                if r.status_code != 200: continue

                for e in r.json():
                    dt = parser.isoparse(e["commence_time"])
                    if not(now <= dt <= now + timedelta(hours=MAX_HOURS_AHEAD)): continue

                    odds = {}
                    totals = {}
                    for bm in e["bookmakers"]:
                        for m in bm["markets"]:
                            if m["key"]=="h2h":
                                for o in m["outcomes"]:
                                    odds[o["name"]] = max(odds.get(o["name"],0), o["price"])
                            if m["key"]=="totals":
                                for o in m["outcomes"]:
                                    totals[o["name"]] = max(totals.get(o["name"],0), o["price"])

                    # Value pick
                    pick = generate_value_pick({
                        "home": e["home_team"],
                        "away": e["away_team"],
                        "league": league,
                        "odds": {"home": odds.get(e["home_team"]),
                                 "away": odds.get(e["away_team"]),
                                 "draw": odds.get("Draw")}
                    })

                    # Sprawdzenie duplikatów
                    if not any(c for c in coupons if c["home"]==e["home_team"] and c["away"]==e["away_team"] and c["sent_date"]==str(now.date())):
                        # Dodaj do value picks
                        if pick:
                            stake = calc_kelly_stake(bankroll, pick["odds"], pick["val"])
                            if stake>0:
                                value_picks.append({
                                    "home": e["home_team"],
                                    "away": e["away_team"],
                                    "league": league,
                                    "sel": pick["sel"],
                                    "odds": pick["odds"],
                                    "val": pick["val"],
                                    "stake": stake,
                                    "dt": dt
                                })
                                bankroll -= stake

                        # BTTS / Over 2.5
                        btts_types = []
                        # BTTS
                        btts_odds = odds.get(e["home_team"]) and odds.get(e["away_team"])
                        if btts_odds:
                            btts_types.append({"type":"BTTS","odds":2.0,"val":0.02,"tier":"B","stake":0.5})
                        # Over 2.5
                        over_odds = totals.get("Over 2.5")
                        if over_odds:
                            btts_types.append({"type":"Over 2.5","odds":over_odds,"val":0.02,"tier":"B","stake":0.5})
                        if btts_types:
                            btts_over_picks.append({
                                "home": e["home_team"],
                                "away": e["away_team"],
                                "league": league,
                                "types": btts_types,
                                "dt": dt
                            })
                break
            except: continue

    # --- Wyślij value picks ---
    for match in value_picks:
        coupons.append({
            "home": match["home"],
            "away": match["away"],
            "picked": match["sel"],
            "odds": match["odds"],
            "stake": match["stake"],
            "league": match["league"],
            "status":"pending",
            "win_val":0,
            "sent_date":str(now.date())
        })
        send_msg(format_value_card(match))

    # --- Wyślij BTTS / Over ---
    for match in btts_over_picks:
        send_msg(format_btts_over_card(match))

    save_bankroll(bankroll)
    save_json(COUPONS_FILE, coupons)

# ================= STATS =================
def send_stats():
    coupons = load_json(COUPONS_FILE, [])
    bankroll = load_bankroll()
    now = datetime.now(timezone.utc)

    def calc_league_stats(c_list):
        stats = defaultdict(lambda: {"types":0,"won":0,"lost":0})
        for c in c_list:
            stats[c["league"]]["types"]+=1
            stats[c["league"]]["won"]+=c.get("win_val",0)
            if c["status"]=="lost":
                stats[c["league"]]["lost"]+=c.get("stake",0)
        return stats

    def format_compact_stats(stats_dict):
        msg=""
        best_league=None
        best_profit=float('-inf')
        for league, data in stats_dict.items():
            profit = data["won"]-data["lost"]
            if profit>best_profit:
                best_profit=profit
                best_league=league
            info=LEAGUE_INFO.get(league,{"flag":"🎯"})
            msg+=f"{info['flag']} {info['name']}: {data['types']} typów | 🟢 {round(data['won'],2)} | 🔴 {round(data['lost'],2)} | 💎 {round(profit,2)}\n"
        return msg,best_league,best_profit

    # --- DZIENNE ---
    today_coupons=[c for c in coupons if c.get("sent_date")==str(now.date()) and c["status"]!="pending"]
    if today_coupons:
        stats=calc_league_stats(today_coupons)
        stats_msg,best_league,best_profit=format_compact_stats(stats)
        send_msg(f"📊 <b>Statystyki dzienne</b> | {str(now.date())}\n💰 Bankroll: {round(bankroll,2)} PLN\n\n{stats_msg}🏆 Najbardziej dochodowa liga: {LEAGUE_INFO.get(best_league,{'name':best_league})['name']} ({round(best_profit,2)} PLN)", target="results")

    # --- TYGODNIOWE ---
    if now.weekday()==6:
        week_coupons=[c for c in coupons if parser.isoparse(c.get("sent_date")).isocalendar()[1]==now.isocalendar()[1] and c["status"]!="pending"]
        if week_coupons:
            stats=calc_league_stats(week_coupons)
            stats_msg,best_league,best_profit=format_compact_stats(stats)
            send_msg(f"📊 <b>Statystyki tygodniowe</b> | tydzień: {now.isocalendar()[1]}\n💰 Bankroll: {round(bankroll,2)} PLN\n\n{stats_msg}🏆 Najbardziej dochodowa liga: {LEAGUE_INFO.get(best_league,{'name':best_league})['name']} ({round(best_profit,2)} PLN)", target="results")

    # --- MIESIĘCZNE ---
    tomorrow=now+timedelta(days=1)
    if tomorrow.day==1:
        month_coupons=[c for c in coupons if parser.isoparse(c.get("sent_date")).month==now.month and c["status"]!="pending"]
        if month_coupons:
            stats=calc_league_stats(month_coupons)
            stats_msg,best_league,best_profit=format_compact_stats(stats)
            send_msg(f"📊 <b>Statystyki miesięczne</b> | miesiąc: {now.month}\n💰 Bankroll: {round(bankroll,2)} PLN\n\n{stats_msg}🏆 Najbardziej dochodowa liga: {LEAGUE_INFO.get(best_league,{'name':best_league})['name']} ({round(best_profit,2)} PLN)", target="results")

# ================= MAIN =================