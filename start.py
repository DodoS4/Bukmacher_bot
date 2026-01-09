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
    os.getenv("ODDS_KEY_3")
] if k]

COUPONS_FILE = "coupons.json"
BANKROLL_FILE = "bankroll.json"
START_BANKROLL = 100.0

MAX_HOURS_AHEAD = 48  # 48 godzin do przodu
VALUE_THRESHOLD = 0.035
KELLY_FRACTION = 0.25

# ================= LIGI =================
LEAGUES = [
    "basketball_nba",                  
    "soccer_epl",                      
    "icehockey_nhl",                   
    "soccer_poland_ekstraklasa",      
    "soccer_uefa_champs_league",      
    "soccer_germany_bundesliga",      
    "soccer_italy_serie_a",            
    "basketball_euroleague"            
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

def format_value_card(matches, card_type="VALUE"):
    msg = ""
    for m in matches:
        info = LEAGUE_INFO.get(m["league"], {"name": m["league"], "flag": "🎯"})
        tier = "A" if m.get("edge",0) >= 0.08 else "B"
        msg += (
            f"{info['flag']} {card_type} • {info['name']}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"<b>{m['home']} vs {m['away']}</b>\n"
            f"🕒 {format_match_time(m['dt'])}\n"
            f"🎯 Typ: <b>{m['pick']}</b>\n"
            f"📈 Kurs: <b>{m['odds']}</b>\n"
            f"💎 Edge: <b>+{round(m.get('edge',0)*100,2)}%</b>\n"
            f"🏷 Tier: <b>{tier}</b>\n"
            f"💰 Stawka: <b>{m['stake']} PLN</b>\n\n"
        )
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
    probs = no_vig_probs({"home": h_o, "away": a_o, "draw": d_o})
    p = {match["home"]: probs.get("home",0), match["away"]: probs.get("away",0), "Remis": probs.get("draw",0)*0.9}

    min_odds = MIN_ODDS.get(match["league"], 2.5)
    best = None
    for sel, prob in p.items():
        odds = h_o if sel==match["home"] else a_o if sel==match["away"] else d_o
        if odds and odds >= min_odds:
            edge = prob - (1/odds)
            if edge >= VALUE_THRESHOLD:
                if not best or edge > best["val"]:
                    best = {"pick": sel, "odds": odds, "edge": edge}
    return best

def generate_btts_over_pick(match):
    # prosty dummy pick BTTS / Over 2.5
    # np. każdy mecz > 2.5 kurs 1.8
    return {"pick": "BTTS/Over", "odds": 1.8}

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

    value_matches = []
    btts_over_matches = []

    for league in LEAGUES:
        for key in API_KEYS:
            try:
                r = requests.get(
                    f"https://api.the-odds-api.com/v4/sports/{league}/odds",
                    params={"apiKey": key,"markets":"h2h","regions":"eu"},
                    timeout=10
                )
                if r.status_code != 200: continue

                for e in r.json():
                    dt = parser.isoparse(e["commence_time"])
                    if not(now <= dt <= now + timedelta(hours=MAX_HOURS_AHEAD)):
                        continue

                    odds = {}
                    for bm in e["bookmakers"]:
                        for m in bm["markets"]:
                            if m["key"]=="h2h":
                                for o in m["outcomes"]:
                                    odds[o["name"]] = max(odds.get(o["name"],0), o["price"])

                    match_data = {
                        "home": e["home_team"],
                        "away": e["away_team"],
                        "league": league,
                        "odds": {"home": odds.get(e["home_team"]), "away": odds.get(e["away_team"]), "draw": odds.get("Draw")},
                        "dt": dt
                    }

                    # Value pick
                    pick_val = generate_value_pick(match_data)
                    if pick_val and not any(c for c in coupons if c["home"]==e["home_team"] and c["away"]==e["away_team"] and c["type"]=="value" and c["sent_date"]==str(now.date())):
                        stake = calc_kelly_stake(bankroll, pick_val["odds"], pick_val["edge"])
                        bankroll -= stake
                        coupons.append({
                            "home": e["home_team"],
                            "away": e["away_team"],
                            "picked": pick_val["pick"],
                            "odds": pick_val["odds"],
                            "stake": stake,
                            "league": league,
                            "status": "pending",
                            "win_val": 0,
                            "sent_date": str(now.date()),
                            "type": "value",
                            "dt": str(dt)
                        })
                        value_matches.append({
                            "home": e["home_team"],
                            "away": e["away_team"],
                            "pick": pick_val["pick"],
                            "odds": pick_val["odds"],
                            "edge": pick_val["edge"],
                            "stake": stake,
                            "dt": dt,
                            "league": league
                        })

                    # BTTS/Over pick
                    pick_btts = generate_btts_over_pick(match_data)
                    if pick_btts and not any(c for c in coupons if c["home"]==e["home_team"] and c["away"]==e["away_team"] and c["type"]=="btts_over" and c["sent_date"]==str(now.date())):
                        stake = calc_kelly_stake(bankroll, pick_btts["odds"], 0.02)
                        bankroll -= stake
                        coupons.append({
                            "home": e["home_team"],
                            "away": e["away_team"],
                            "picked": pick_btts["pick"],
                            "odds": pick_btts["odds"],
                            "stake": stake,
                            "league": league,
                            "status": "pending",
                            "win_val": 0,
                            "sent_date": str(now.date()),
                            "type": "btts_over",
                            "dt": str(dt)
                        })
                        btts_over_matches.append({
                            "home": e["home_team"],
                            "away": e["away_team"],
                            "pick": pick_btts["pick"],
                            "odds": pick_btts["odds"],
                            "stake": stake,
                            "dt": dt,
                            "league": league
                        })

                break
            except: continue

    save_bankroll(bankroll)
    save_json(COUPONS_FILE, coupons)

    # Wysyłamy jedną wiadomość VALUE i BTTS/Over osobno
    if value_matches:
        send_msg(format_value_card(value_matches, card_type="VALUE"))
    if btts_over_matches:
        send_msg(format_value_card(btts_over_matches, card_type="BTTS/Over"))

# ================= MAIN =================
if __name__ == "__main__":
    if "--stats" in sys.argv:
        # tutaj wywołaj stats.py
        from stats import main as stats_main
        stats_main()
    else:
        run()