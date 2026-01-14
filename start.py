import requests
import json
import os
from datetime import datetime, timezone, timedelta
import random  # przykładowa symulacja True Odds

# ================= CONFIG =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")
API_KEYS = [os.getenv(f"ODDS_KEY{i}") for i in ["", "_2", "_3", "_4", "_5"]]
API_KEYS = [k for k in API_KEYS if k]
COUPONS_FILE = "coupons.json"
TAX_PL = 0.88  # 12% podatek

# ================= TELEGRAM =================
def send_msg(txt):
    if not T_TOKEN or not T_CHAT:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
            json={"chat_id": T_CHAT, "text": txt, "parse_mode": "HTML"}
        )
    except Exception as e:
        print(f"[ERROR] Telegram: {e}")

# ================= LOAD/STORE COUPONS =================
def load_coupons():
    if not os.path.exists(COUPONS_FILE):
        return []
    try:
        with open(COUPONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def save_coupons(coupons):
    with open(COUPONS_FILE, "w", encoding="utf-8") as f:
        json.dump(coupons, f, indent=2, ensure_ascii=False)

# ================= FETCH SCORES/ODDS =================
def fetch_offers(league_key):
    for key in API_KEYS:
        try:
            r = requests.get(f"https://api.the-odds-api.com/v4/sports/{league_key}/odds/", 
                             params={"apiKey": key, "regions": "eu", "markets": "h2h"})
            if r.status_code == 200:
                return r.json()
        except:
            continue
    return []

# ================= EDGE CALC =================
def calculate_edge(c):
    """
    Oblicza Edge zakładu.
    True Odds są symulowane – w praktyce można tu podstawić własną analizę.
    """
    true_prob = random.uniform(0.4, 0.8)  # losowa szansa na wygraną
    true_odds = 1 / true_prob
    c["true_odds"] = round(true_odds, 2)
    c["edge"] = round((true_odds / c["odds"] - 1) * 100, 2)

def classify_coupon(c):
    """
    Rozdziela zakłady na PEWNIAKI i VALUE
    """
    if c["odds"] <= 1.50 and c["edge"] >= 0:
        c["type"] = "PEWNIAK"
    elif c["edge"] > 0:
        c["type"] = "VALUE"
    else:
        c["type"] = "STANDARD"

# ================= CREATE COUPONS =================
def create_coupons():
    # Tutaj dodajemy ligi, np. NBA, Euroleague, NHL
    leagues = ["basketball_nba", "basketball_euroleague", "icehockey_nhl"]
    coupons = []

    for league in leagues:
        offers = fetch_offers(league)
        for o in offers:
            # Przykładowa struktura kuponu
            try:
                home = o["home_team"]
                away = o["away_team"]
                for h2h in o["bookmakers"][0]["markets"][0]["outcomes"]:
                    pick = h2h["name"]
                    odds = float(h2h["price"])
                    c = {
                        "home": home,
                        "away": away,
                        "pick": pick,
                        "odds": odds,
                        "stake": 100,
                        "status": "PENDING",
                        "league_key": league,
                        "date": o.get("commence_time", datetime.now(timezone.utc).isoformat())
                    }
                    calculate_edge(c)
                    classify_coupon(c)
                    coupons.append(c)
            except:
                continue
    save_coupons(coupons)
    print(f"[INFO] Dodano {len(coupons)} kuponów")
    return coupons

# ================= SEND COUPONS =================
def send_coupons(coupons):
    for c in coupons:
        txt = (f"📌 <b>{c['home']} - {c['away']}</b>\n"
               f"🎯 Typ: {c['pick']} | Kurs: {c['odds']} | Edge: {c['edge']}% | Typ zakładu: {c['type']}")
        send_msg(txt)

# ================= MAIN =================
if __name__ == "__main__":
    coupons = create_coupons()
    send_coupons(coupons)
    print("[INFO] Wysłano wszystkie kupony na Telegram")