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

# Lista kluczy Odds API
KEYS_POOL = [
    os.getenv("ODDS_KEY"),
    os.getenv("ODDS_KEY_2"),
    os.getenv("ODDS_KEY_3"),
    os.getenv("ODDS_KEY_4"),
    os.getenv("ODDS_KEY_5")
]
API_KEYS = [k for k in KEYS_POOL if k]

COUPONS_FILE = "coupons.json"
DAILY_LIMIT = 20
STAKE = 5.0
MAX_HOURS_AHEAD = 48  # maksymalnie 48h do rozpoczęcia meczu

# Ligii do monitorowania (slug The Odds API)
LEAGUES = [
    "soccer_epl",
    "soccer_spain_la_liga",
    "soccer_italy_serie_a",
    "soccer_germany_bundesliga",
    "soccer_france_ligue_one",
    "basketball_nba",
    "soccer_netherlands_eredivisie",    # Holandia
    "soccer_portugal_primeira_liga"     # Portugalia
]

# ================= WYSYŁKA =================
def send_msg(text, target="types"):
    chat_id = T_CHAT_RESULTS if target=="results" else T_CHAT
    if not T_TOKEN or not chat_id: return
    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode":"Markdown"}, timeout=15)
    except:
        pass

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
    today_sent = [c for c in coupons if c.get("date","")[:10]==today]
    return len(today_sent) >= DAILY_LIMIT

# ================= POBIERANIE MECZÓW Z ODDS API =================
def get_upcoming_matches(league):
    matches = []
    for api_key in API_KEYS:
        try:
            url = f"https://api.the-odds-api.com/v4/sports/{league}/odds"
            params = {"apiKey": api_key, "regions":"eu","markets":"h2h","oddsFormat":"decimal"}
            r = requests.get(url, params=params, timeout=15)
            if r.status_code != 200:
                continue
            data = r.json()
            for event in data:
                home = event["home_team"]
                away = event["away_team"]
                commence = event["commence_time"]
                if event.get("bookmakers"):
                    b = event["bookmakers"][0]
                    h_odds = b["markets"][0]["outcomes"][0]["price"]
                    a_odds = b["markets"][0]["outcomes"][1]["price"]
                    matches.append({
                        "home": home,
                        "away": away,
                        "odds": {"home": h_odds,"away": a_odds},
                        "commence_time": commence
                    })
            if matches:
                break
        except:
            continue
    return matches

# ================= GENEROWANIE TYPU (value bet) =================
def generate_pick(match):
    home = match["home"]
    away = match["away"]
    h_odds = match["odds"]["home"]
    a_odds = match["odds"]["away"]

    prob_home = random.uniform(0.4,0.6)
    prob_away = 1 - prob_home

    val_home = prob_home - 1/h_odds
    val_away = prob_away - 1/a_odds

    if val_home > 0 and val_home >= val_away:
        return {"selection": home, "odds": h_odds, "date": match["commence_time"], "home": home, "away": away}
    elif val_away > 0:
        return {"selection": away, "odds": a_odds, "date": match["commence_time"], "home": home, "away": away}
    return None

# ================= GENERUJ OFERTY =================
def simulate_offers():
    coupons = load_coupons()
    if daily_limit_reached(coupons):
        return

    now = datetime.now(timezone.utc)

    for league in LEAGUES:
        matches = get_upcoming_matches(league)
        if not matches:
            continue

        for match in matches:
            match_dt = parser.isoparse(match["commence_time"])
            if match_dt < now or match_dt > now + timedelta(hours=MAX_HOURS_AHEAD):
                continue
            if any(c["home"]==match["home"] and c["away"]==match["away"] for c in coupons):
                continue

            pick = generate_pick(match)
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

                match_dt_str = match_dt.strftime("%d-%m-%Y %H:%M UTC")
                text = (
                    f"📊 *NOWA OFERTA* ({league.upper()})\n"
                    f"🏟️ {pick['home']} vs {pick['away']}\n"
                    f"🕓 {match_dt_str}\n"
                    f"✅ Twój typ: *{pick['selection']}*\n"
                    f"💰 Stawka: {STAKE} PLN\n"
                    f"🎯 Kurs: {pick['odds']}"
                )
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
        match_dt_str = end_time.strftime("%d-%m-%Y %H:%M UTC")
        icon="✅" if c["status"]=="win" else "❌"
        text=f"{icon} *KUPON ROZLICZONY* ({c['league'].upper()})\n🏟️ {c['home']} vs {c['away']}\n🕓 {match_dt_str}\n🎯 Twój typ: {c['picked']}\n💰 Bilans: {profit:+.2f} PLN\n🎯 Kurs: {c['odds']}"
        send_msg(text,target="results")
        updated=True
    if updated:
        save_coupons(coupons)

# ================= RAPORT TYGODNIOWY =================
def send_weekly_report():
    coupons = load_coupons()
    now = datetime.now(timezone.utc)
    last_week = now - timedelta(days=7)

    completed = [c for c in coupons if c.get("status") in ["win","loss"] and parser.isoparse(c["date"]) > last_week]
    if not completed: return

    wins = len([c for c in completed if c["status"]=="win"])
    total = len(completed)
    profit = sum((c["win_val"]-c["stake"]) if c["status"]=="win" else -c["stake"] for c in completed)
    icon = "🚀" if profit >= 0 else "📉"

    text = (
        f"📅 *PODSUMOWANIE TYGODNIA*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ Trafione: {wins}/{total}\n"
        f"💰 Zysk/Strata: {profit:+.2f} PLN {icon}\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )
    send_msg(text,target="results")

# ================= START =================
def run():
    simulate_offers()
    check_results()
    now = datetime.now(timezone.utc)
    if now.weekday()==0 and now.hour==8:
        send_weekly_report()

if __name__=="__main__":
    run()
