import requests, json, os

API_KEY = os.getenv("ODDS_KEY")
BANKROLL_FILE = "bankroll.json"
COUPONS_FILE = "coupons.json"
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS")

def settle():
    with open(BANKROLL_FILE, "r") as f: br = json.load(f)
    with open(COUPONS_FILE, "r") as f: coupons = json.load(f)
    
    leagues = list(set(c["league"] for c in coupons if c["status"] == "pending"))
    updated = False

    for lg in leagues:
        r = requests.get(f"https://api.the-odds-api.com/v4/sports/{lg}/scores/", params={"apiKey": API_KEY, "daysFrom": 3})
        if r.status_code != 200: continue
        results = r.json()

        for c in coupons:
            if c["status"] == "pending" and c["league"] == lg:
                res = next((s for s in results if s["home_team"] == c["home"] and s["away_team"] == c["away"] and s["completed"]), None)
                if res:
                    if res["winner"] == c["pick"]:
                        c["status"] = "won"
                        br["bankroll"] += c["possible_win"]
                        msg = f"✅ WYGRANA: {c['home']}-{c['away']} (+{round(c['possible_win']-c['stake'],2)} PLN)"
                    else:
                        c["status"] = "lost"
                        msg = f"❌ PRZEGRANA: {c['home']}-{c['away']} (-{c['stake']} PLN)"
                    
                    requests.post(f"https://api.telegram.org/bot{T_TOKEN}/sendMessage", json={"chat_id":T_CHAT_RESULTS,"text":msg})
                    updated = True

    if updated:
        with open(BANKROLL_FILE, "w") as f: json.dump(br, f)
        with open(COUPONS_FILE, "w") as f: json.dump(coupons, f, indent=2)

if __name__ == "__main__":
    settle()
