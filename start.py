import requests, json, os
from datetime import datetime, timedelta, timezone

T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")
API_KEYS = [os.getenv(f"ODDS_KEY{i}") for i in ["", "_2", "_3", "_4", "_5"]]
API_KEYS = [k for k in API_KEYS if k]

COUPONS_FILE = "coupons.json"

# Limit czasu do przodu: 48 godzin
MAX_HOURS_AHEAD = 48

def send_msg(txt):
    if not T_TOKEN or not T_CHAT: return
    try:
        requests.post(f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
                      json={"chat_id": T_CHAT, "text": txt, "parse_mode": "HTML"})
    except: pass

def load_coupons():
    if not os.path.exists(COUPONS_FILE): return []
    try:
        with open(COUPONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except: return []

def save_coupons(coupons):
    with open(COUPONS_FILE, "w", encoding="utf-8") as f:
        json.dump(coupons, f, indent=2, ensure_ascii=False)

def fetch_odds(league_key):
    now = datetime.now(timezone.utc)
    future_limit = now + timedelta(hours=MAX_HOURS_AHEAD)
    for key in API_KEYS:
        try:
            r = requests.get(
                f"https://api.the-odds-api.com/v4/sports/{league_key}/odds/",
                params={"apiKey": key, "regions":"eu", "markets":"h2h", "oddsFormat":"decimal"}
            )
            if r.status_code != 200:
                continue
            data = r.json()
            # Filtrowanie po max 48h
            data = [m for m in data if now <= datetime.fromisoformat(m["commence_time"].replace("Z","+00:00")) <= future_limit]
            return data
        except: continue
    return []

def generate_coupons():
    coupons = load_coupons()
    leagues = ["basketball_nba", "basketball_euroleague"]  # tu dodasz swoje ligi

    for league in leagues:
        games = fetch_odds(league)
        for g in games:
            home, away = g["home_team"], g["away_team"]
            match_time = datetime.fromisoformat(g["commence_time"].replace("Z","+00:00"))
            
            # Przykład: pewniak/value (tu możesz wstawić własną logikę)
            pick = home
            odds = g["bookmakers"][0]["markets"][0]["outcomes"][0]["price"]
            stake = 100
            type_ = "PEWNY" if odds < 1.5 else "VALUE"

            coupon = {
                "home": home,
                "away": away,
                "pick": pick,
                "odds": odds,
                "stake": stake,
                "status": "PENDING",
                "league": g.get("sport_title", league),
                "league_key": league,
                "type": type_,
                "date": match_time.isoformat(),
            }
            coupons.append(coupon)
            txt = f"📌 Nowy kupon: {home} - {away}\nTyp: {pick} ({type_})\nKurs: {odds}\nData: {match_time.strftime('%d.%m.%Y %H:%M')}"
            send_msg(txt)
    save_coupons(coupons)
    print(f"[INFO] Dodano {len(coupons)} kuponów")

if __name__ == "__main__":
    generate_coupons()