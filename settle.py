import requests, json, os
from datetime import datetime, timezone

T_TOKEN = os.getenv("T_TOKEN")
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS")
API_KEYS = [os.getenv(f"ODDS_KEY{i}") for i in ["", "_2", "_3", "_4", "_5"] if os.getenv(f"ODDS_KEY{i}")]
FILE = "coupons_notax.json"
TAX = 1.0  # NO TAX

def tg(msg):
    if T_TOKEN and T_CHAT_RESULTS:
        try:
            requests.post(
                f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
                json={"chat_id": T_CHAT_RESULTS, "text": msg, "parse_mode": "HTML"}
            )
        except:
            pass

def load():
    if os.path.exists(FILE):
        with open(FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except:
                return []
    return []

def save(data):
    with open(FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def run():
    coupons = load()
    pending = [c for c in coupons if c.get("status")=="PENDING"]
    if not pending: return

    for c in pending:
        # Szukamy odpowiedniego API key
        for key in API_KEYS:
            url = f"https://api.the-odds-api.com/v4/sports/{c['league'].lower().replace(' ','_')}/scores/"
            try:
                r = requests.get(url, params={"apiKey": key, "daysFrom":3})
                if r.status_code != 200: continue
                scores = r.json()
            except:
                continue

            # Szukamy meczu
            match = next((m for m in scores if m['home_team']==c['home'] or m['away_team']==c['home']), None)
            if not match or not match.get("completed"): continue

            try:
                score_map = {s['name']: int(s['score']) for s in match.get("scores",[])}
                h_score = score_map.get(c['home'])
                a_score = score_map.get(c['away'])
                if h_score is None or a_score is None: continue

                winner = c['home'] if h_score > a_score else c['away']
                if c['pick'] == winner:
                    c['status'] = "WON"
                    profit = c['stake'] * c['odds'] * TAX - c['stake']
                    c['profit'] = round(profit,2)
                    emoji = "✅"
                    msg = f"{emoji} <b>ROZLICZONO: {c['home']} - {c['away']}</b>\nWynik: {h_score}:{a_score}\nTyp: {c['pick']} | Zysk: <b>+{c['profit']} zł</b>"
                else:
                    c['status'] = "LOST"
                    c['profit'] = -c['stake']
                    emoji = "❌"
                    msg = f"{emoji} <b>ROZLICZONO: {c['home']} - {c['away']}</b>\nWynik: {h_score}:{a_score}\nTyp: {c['pick']} | Strata: <b>{c['profit']} zł</b>"

                c['settled_at'] = datetime.now(timezone.utc).isoformat()
                tg(msg)
                break
            except:
                continue

    save(coupons)

if __name__=="__main__":
    run()