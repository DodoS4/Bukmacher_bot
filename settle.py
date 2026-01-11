import requests, json, os
from datetime import datetime

T_TOKEN = os.getenv("T_TOKEN")
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS")
TAX_PL = 0.88
API_KEYS = [os.getenv(f"ODDS_KEY{i}") for i in ["", "_2", "_3", "_4", "_5"]]
API_KEYS = [k for k in API_KEYS if k]
COUPONS_FILE = "coupons.json"

def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f: return json.load(f)
        except: pass
    return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f: json.dump(data, f, indent=2)

def send_res(txt):
    target = T_CHAT_RESULTS if T_CHAT_RESULTS else os.getenv("T_CHAT")
    try: requests.post(f"https://api.telegram.org/bot{T_TOKEN}/sendMessage", json={"chat_id": target, "text": txt, "parse_mode": "HTML"})
    except: pass

def get_scores(l_key):
    for key in API_KEYS:
        r = requests.get(f"https://api.the-odds-api.com/v4/sports/{l_key}/scores", params={"apiKey": key, "daysFrom": 3})
        if r.status_code == 200: return r.json()
    return None

def run_settler():
    coupons = load_json(COUPONS_FILE, [])
    pending_leagues = {c['league_key'] for c in coupons if c['status'] == 'PENDING'}
    results_cache = {l: get_scores(l) for l in pending_leagues if get_scores(l)}

    for c in coupons:
        if c['status'] != 'PENDING': continue
        match = next((m for m in results_cache.get(c['league_key'], []) if m['home_team'] == c['home'] and m['completed']), None)
        if match:
            s = {s['name']: int(s['score']) for s in match['scores']}
            h, a = s[c['home']], s[c['away']]
            win = c['home'] if h > a else (c['away'] if a > h else "Draw")
            if c['pick'] == win:
                c['status'] = 'WON'
                # Zysk liczony z uwzględnieniem 12% podatku od CAŁEJ kwoty wygranej
                payout = c['stake'] * c['odds'] * TAX_PL
                profit = round(payout - c['stake'], 2)
                send_res(f"✅ <b>WYGRANA!</b>\n{c['home']}-{c['away']}\nWynik: {h}:{a}\nZysk netto: <b>{profit}j</b>")
            else:
                c['status'] = 'LOST'
                send_res(f"❌ <b>PRZEGRANA</b>\n{c['home']}-{c['away']}\nWynik: {h}:{a}\nStrata: -{c['stake']}j")
    save_json(COUPONS_FILE, coupons)

if __name__ == "__main__": run_settler()
