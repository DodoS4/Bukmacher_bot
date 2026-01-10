import requests, json, os
from datetime import datetime, timezone

# ================= CONFIG =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS")
API_KEYS = [k for k in [os.getenv("ODDS_KEY"), os.getenv("ODDS_KEY_2")] if k]
BANKROLL_FILE = "bankroll.json"
COUPONS_FILE = "coupons.json"

# ================= UTILS =================
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

# ================= SETTLE LOGIC =================
def settle():
    bankroll_data = load_json(BANKROLL_FILE, {"bankroll": 10000.0})
    bankroll = bankroll_data["bankroll"]
    coupons = load_json(COUPONS_FILE, [])
    
    pending = [c for c in coupons if c["status"] == "pending"]
    if not pending:
        print("[DEBUG] Brak oczekujących zakładów do rozliczenia.")
        return

    updated = False
    for c in pending:
        # Sprawdzamy wyniki (używamy pierwszego działającego klucza)
        result = None
        for key in API_KEYS:
            try:
                url = f"https://api.the-odds-api.com/v4/sports/{c['league']}/scores"
                r = requests.get(url, params={"apiKey": key, "daysFrom": 3}, timeout=15)
                if r.status_code == 200:
                    scores = r.json()
                    # Szukamy konkretnego meczu
                    match = next((m for m in scores if m["home_team"] == c["home"] and m["away_team"] == c["away"] and m["completed"]), None)
                    if match:
                        # Logika wyłaniania zwycięzcy
                        home_score = next((s["score"] for s in match["scores"] if s["name"] == c["home"]), 0)
                        away_score = next((s["score"] for s in match["scores"] if s["name"] == c["away"]), 0)
                        
                        winner = "Draw"
                        if int(home_score) > int(away_score): winner = c["home"]
                        elif int(away_score) > int(home_score): winner = c["away"]
                        
                        result = "WON" if c["pick"] == winner else "LOST"
                    break
            except: continue

        if result:
            c["status"] = result
            updated = True
            if result == "WON":
                # Dodajemy kwotę NETTO (już z uwzględnionym podatkiem z kuponu)
                win_amount = c["possible_win"]
                bankroll += win_amount
                status_emoji = "✅ WYGRANA"
                profit_text = f"+{round(win_amount - c['stake'], 2)} PLN"
            else:
                status_emoji = "❌ PRZEGRANA"
                profit_text = f"-{c['stake']} PLN"

            send_msg(
                f"{status_emoji}\n"
                f"🏟️ {c['home']} vs {c['away']}\n"
                f"🎯 Typ: {c['pick']} (@{c['odds']})\n"
                f"💰 Wynik: <b>{profit_text}</b>\n"
                f"🏦 Bankroll: {round(bankroll, 2)} PLN"
            )

    if updated:
        bankroll_data["bankroll"] = round(bankroll, 2)
        save_json(BANKROLL_FILE, bankroll_data)
        save_json(COUPONS_FILE, coupons)
        print(f"[DEBUG] Rozliczono zakłady. Nowy bankroll: {bankroll}")

if __name__ == "__main__":
    settle()
