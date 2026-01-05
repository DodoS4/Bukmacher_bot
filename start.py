import requests
import json
import os
from datetime import datetime, timedelta, timezone
from dateutil import parser
import random

# ================= KONFIGURACJA =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")           
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS") 

COUPONS_FILE = "coupons.json"
DAILY_LIMIT = 20
STAKE = 5.0
LEAGUES = ["epl", "laliga", "serie-a", "bundesliga", "ligue-1"]  # kilka lig

# ================= WYSYŁKA =================
def send_msg(text, target="types"):
    chat_id = T_CHAT_RESULTS if target=="results" else T_CHAT
    if not T_TOKEN or not chat_id: return
    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode":"Markdown"}, timeout=15)
    except:
        pass

# ================= POBIERANIE TABELI =================
def get_standings(league_slug):
    url = f"https://api.footballstandings.com/leagues/{league_slug}"
    try:
        r = requests.get(url, timeout=15)
        data = r.json()
        table = {team["team"]["name"]: team["position"] for team in data.get("standings", [])}
        return table
    except:
        return {}

# ================= FORMA DRUŻYN =================
def get_real_form(teams, league_slug):
    form_data = {}
    for team in teams:
        try:
            url = f"https://api.football-data.org/v4/teams/{team}/matches?limit=5"
            headers = {"X-Auth-Token": os.getenv("FOOTBALL_DATA_KEY","")}
            r = requests.get(url, headers=headers, timeout=15)
            data = r.json()
            last_matches = data.get("matches", [])
            wins = 0
            for m in last_matches:
                if m["score"]["winner"] == "HOME_TEAM" and m["homeTeam"]["name"] == team:
                    wins += 1
                elif m["score"]["winner"] == "AWAY_TEAM" and m["awayTeam"]["name"] == team:
                    wins += 1
            form_data[team] = wins / max(1,len(last_matches))
        except:
            form_data[team] = 0.5
    return form_data

# ================= GENEROWANIE TYPU =================
def generate_pick(match, league_table, form_data):
    home = match["home"]
    away = match["away"]

    home_pos = league_table.get(home, 10)
    away_pos = league_table.get(away, 10)
    pos_factor = 0.03 * (away_pos - home_pos)

    home_form = form_data.get(home, 0.5)
    away_form = form_data.get(away, 0.5)
    form_factor = (home_form - away_form) * 0.3

    home_adv = 0.05
    model_prob_home = 0.5 + home_adv + pos_factor + form_factor
    model_prob_home = max(min(model_prob_home,0.8),0.2)
    model_prob_away = 1 - model_prob_home

    home_odds = match["odds"]["home"]
    away_odds = match["odds"]["away"]

    home_value = model_prob_home - 1/home_odds
    away_value = model_prob_away - 1/away_odds

    if home_value > 0 and home_value >= away_value:
        return {"selection": home, "odds": home_odds, "model_prob": model_prob_home, "date": match["commence_time"], "home": home, "away": away}
    elif away_value > 0:
        return {"selection": away, "odds": away_odds, "model_prob": model_prob_away, "date": match["commence_time"], "home": home, "away": away}
    return None

# ================= COUPONS =================
def load_coupons():
    if os.path.exists(COUPONS_FILE):
        try:
            with open(COUPONS_FILE,"r",encoding="utf-8") as f:
                return json.load(f)
        except:
            return []
    return []

def save_coupons(coupons):
    with open(COUPONS_FILE,"w",encoding="utf-8") as f:
        json.dump(coupons[-500:], f, indent=4)

def daily_limit_reached(coupons):
    today = datetime.now(timezone.utc).date().isoformat()
    today_sent = [c for c in coupons if c.get("date","")[:10] == today]
    return len(today_sent) >= DAILY_LIMIT

# ================= POBIERANIE MECZÓW =================
def get_upcoming_matches(league):
    # symulacja meczów – docelowo podpiąć API z kursami i datą meczu
    if league == "epl":
        return [
            {"home":"Arsenal","away":"Chelsea","odds":{"home":1.8,"away":2.0},"commence_time":"2026-01-06T20:00:00Z"},
            {"home":"Liverpool","away":"Man City","odds":{"home":2.1,"away":1.9},"commence_time":"2026-01-06T18:00:00Z"},
        ]
    if league == "laliga":
        return [
            {"home":"Real Madrid","away":"Barcelona","odds":{"home":1.9,"away":1.9},"commence_time":"2026-01-06T22:00:00Z"},
        ]
    return []

# ================= GENERUJ OFERTY =================
def simulate_offers():
    coupons = load_coupons()
    if daily_limit_reached(coupons):
        return

    for league in LEAGUES:
        matches = get_upcoming_matches(league)
        if not matches:
            continue

        teams = set([m["home"] for m in matches] + [m["away"] for m in matches])
        league_table = get_standings(league)
        form_data = get_real_form(teams, league_slug=league)

        for match in matches:
            if any(c["home"]==match["home"] and c["away"]==match["away"] for c in coupons):
                continue

            pick = generate_pick(match, league_table, form_data)
            if pick:
                coupon = {
                    "home": pick["home"],
                    "away": pick["away"],
                    "picked": pick["selection"],
                    "odds": pick["odds"],
                    "stake": STAKE,
                    "status": "pending",
                    "date": pick["date"],
                    "win_val": round(pick["odds"]*STAKE,2),
                    "league": league
                }
                coupons.append(coupon)
                
                text = f"📊 *NOWA OFERTA* ({league.upper()})\n🏟️ {pick['home']} vs {pick['away']}\n🕓 {pick['date']}\n✅ Twój typ: *{pick['selection']}*\n💰 Stawka: {STAKE} PLN"
                send_msg(text,target="types")

    save_coupons(coupons)

# ================= ROZLICZANIE =================
def check_results():
    coupons = load_coupons()
    updated=False
    now=datetime.now(timezone.utc)
    for c in coupons:
        if c.get("status")!="pending": continue
        end_time = parser.isoparse(c["date"])
        if now < end_time + timedelta(hours=4): continue

        winner = random.choice([c["home"],c["away"]])
        c["status"]="win" if winner==c["picked"] else "loss"
        profit = round(c["win_val"]-c["stake"],2) if c["status"]=="win" else -c["stake"]
        icon="✅" if c["status"]=="win" else "❌"
        text=f"{icon} *KUPON ROZLICZONY* ({c['league'].upper()})\n🏟️ {c['home']} vs {c['away']}\n🎯 Twój typ: {c['picked']}\n💰 Bilans: {profit:+.2f} PLN"
        send_msg(text,target="results")
        updated=True
    if updated:
        save_coupons(coupons)

# ================= START =================
def run():
    simulate_offers()
    check_results()

if __name__=="__main__":
    run()
