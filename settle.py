import requests, json, os
from datetime import datetime

COUPONS_FILE = "coupons.json"
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT_RESULTS")
API_KEYS = [os.getenv(f"ODDS_KEY{i}") for i in ["", "_2", "_3", "_4", "_5"]]
API_KEYS = [k for k in API_KEYS if k]
TAX_PL = 0.88  # 12% podatek

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
        json.dump(coupons, f, indent=2)

def fetch_scores(league_key):
    for key in API_KEYS:
        try:
            r = requests.get(f"https://api.the-odds-api.com/v4/sports/{league_key}/scores/",
                             params={"apiKey": key, "daysFrom": 3})
            if r.status_code == 200:
                return r.json()
        except: continue
    return []

def run_settler():
    coupons = load_coupons()
    pending = [c for c in coupons if c.get("status")=="PENDING"]
    if not pending: return

    leagues = {c["league_key"] for c in pending}
    for l_key in leagues:
        scores = fetch_scores(l_key)
        for c in coupons:
            if c.get("status")!="PENDING" or c["league_key"] != l_key: continue

            match_score = next((s for s in scores if s["home_team"]==c["home"] or s["away_team"]==c["home"]), None)
            if match_score and match_score.get("completed"):
                try:
                    s_dict = {s["name"]: int(s["score"]) for s in match_score["scores"]}
                    h_score = s_dict.get(c["home"])
                    a_score = s_dict.get(c["away"])
                    if h_score is None or a_score is None: continue

                    winner = c["home"] if h_score > a_score else c["away"]
                    c["status"] = "WON" if c["pick"] == winner else "LOST"

                    if c["status"]=="WON":
                        profit = (c["stake"] * c["odds"] * TAX_PL) - c["stake"]
                        c["profit"] = round(profit,2)
                        txt = f"✅ ROZLICZONO: {c['home']} - {c['away']}\nTyp: {c['pick']} | Zysk: +{round(profit,2)} zł"
                    else:
                        c["profit"] = -c["stake"]
                        txt = f"❌ ROZLICZONO: {c['home']} - {c['away']}\nTyp: {c['pick']} | Strata: -{c['stake']} zł"
                    c["settled_at"] = datetime.utcnow().isoformat()
                    send_msg(txt)
                except: continue
    save_coupons(coupons)

if __name__=="__main__":
    run_settler()