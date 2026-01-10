import requests, json, os
from datetime import datetime, timezone

# ================= CONFIG =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS")
API_KEYS = [k for k in [os.getenv("ODDS_KEY"), os.getenv("ODDS_KEY_2"), os.getenv("ODDS_KEY_3")] if k]
BANKROLL_FILE = "bankroll.json"
COUPONS_FILE = "coupons.json"

def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def send_msg(txt):
    if not T_TOKEN or not T_CHAT_RESULTS: return
    try:
        requests.post(
            f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
            json={"chat_id": T_CHAT_RESULTS, "text": txt, "parse_mode": "HTML"},
            timeout=10
        )
    except: pass

def settle():
    bankroll_data = load_json(BANKROLL_FILE, {"bankroll": 10000.0})
    bankroll = bankroll_data["bankroll"]
    coupons = load_json(COUPONS_FILE, [])
    
    pending = [c for c in coupons if c["status"] == "PENDING"]
    if not pending:
        print("[DEBUG] Brak oczekujących zakładów.")
        return

    updated = False
    for c in pending:
        result = None
        for key in API_KEYS:
            try:
                url = f"https://api.the-odds-api.com/v4/sports/{c['league']}/scores"
                r = requests.get(url, params={"apiKey": key, "daysFrom": 3}, timeout=15)
                if r.status_code == 200:
                    scores = r.json()
                    match = next((m for m in scores if m["home_team"] == c["home"] and m["away_team"] == c["away"] and m["completed"]), None)
                    if match:
                        h_score = next((s["score"] for s in match["scores"] if s["name"] == c["home"]), 0)
                        a_score = next((s["score"] for s in match["scores"] if s["name"] == c["away"]), 0)
                        
                        winner = "Draw"
                        if int(h_score) > int(a_score): winner = c["home"]
                        elif int(a_score) > int(h_score): winner = c["away"]
                        
                        result = "WON" if c["pick"] == winner else "LOST"
                    break
            except: continue

        if result:
            c["status"] = result
            updated = True
            if result == "WON":
                win_amt = c["possible_win"]
                bankroll += win_amt
                msg = f"✅ <b>WYGRANA</b>\n{c['home']} - {c['away']}\nTyp: {c['pick']} (@{c['odds']})\nZysk netto: +{round(win_amt - c['stake'], 2)} PLN"
            else:
                msg = f"❌ <b>PRZEGRANA</b>\n{c['home']} - {c['away']}\nTyp: {c['pick']}\nStrata: -{c['stake']} PLN"
            
            send_msg(f"{msg}\n🏦 Bankroll: {round(bankroll, 2)} PLN")

    if updated:
        bankroll_data["bankroll"] = round(bankroll, 2)
        save_json(BANKROLL_FILE, bankroll_data)
        save_json(COUPONS_FILE, coupons)

if __name__ == "__main__":
    settle()
