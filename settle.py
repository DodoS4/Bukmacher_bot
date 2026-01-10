import requests, json, os
from datetime import datetime, timezone

# ================= CONFIG =================
COUPONS_FILE = "coupons.json"
BANKROLL_FILE = "bankroll.json"
# Używamy tego samego klucza co w start.py
ODDS_KEY = os.getenv("ODDS_KEY")
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS")

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
            json={"chat_id": T_CHAT_RESULTS, "text": txt, "parse_mode": "HTML"}
        )
    except: pass

# ================= SETTLE LOGIC =================
def settle_bets():
    coupons = load_json(COUPONS_FILE, [])
    bankroll_data = load_json(BANKROLL_FILE, {"bankroll": 0.0})
    current_bankroll = bankroll_data.get("bankroll", 0.0)
    
    updated = False
    pending_bets = [c for c in coupons if c["status"] == "pending"]
    
    if not pending_bets:
        print("[DEBUG] Brak oczekujących zakładów do rozliczenia.")
        return

    # Pobieramy wyniki dla lig, które mają aktywne zakłady
    active_leagues = list(set(c["league"] for c in pending_bets))
    
    for league in active_leagues:
        print(f"[DEBUG] Sprawdzam wyniki dla ligi: {league}")
        url = f"https://api.the-odds-api.com/v4/sports/{league}/scores/"
        params = {"apiKey": ODDS_KEY, "daysFrom": 3}
        
        try:
            r = requests.get(url, params=params)
            if r.status_code != 200: continue
            results = r.json()
            
            for res in results:
                if not res.get("completed"): continue
                
                home_team = res["home_team"]
                away_team = res["away_team"]
                
                # Szukamy kuponu pasującego do tego meczu
                for c in coupons:
                    if c["status"] == "pending" and c["home"] == home_team and c["away"] == away_team:
                        # Wyciągamy wynik końcowy
                        scores = res.get("scores", [])
                        if not scores: continue
                        
                        h_score = int(next(s["score"] for s in scores if s["name"] == home_team))
                        a_score = int(next(s["score"] for s in scores if s["name"] == away_team))
                        
                        winner = home_team if h_score > a_score else away_team if a_score > h_score else "Draw"
                        
                        # Rozstrzygnięcie
                        if c["pick"] == winner:
                            c["status"] = "won"
                            current_bankroll += c["possible_win"]
                            msg = f"✅ <b>WYGRANA!</b>\n{home_team} - {away_team}\nTyp: {c['pick']} ({h_score}:{a_score})\n💰 Zwrot: <b>{c['possible_win']} PLN</b>"
                        else:
                            c["status"] = "lost"
                            msg = f"❌ <b>PRZEGRANA</b>\n{home_team} - {away_team}\nTyp: {c['pick']} ({h_score}:{a_score})"
                        
                        print(f"[DEBUG] Rozliczono: {home_team}-{away_team} jako {c['status']}")
                        send_msg(msg)
                        updated = True
        except Exception as e:
            print(f"[ERROR] Problem z ligą {league}: {e}")

    if updated:
        save_json(COUPONS_FILE, coupons)
        save_json(BANKROLL_FILE, {"bankroll": round(current_bankroll, 2)})
        print(f"[DEBUG] Bankroll zaktualizowany: {round(current_bankroll, 2)} PLN")

if __name__ == "__main__":
    settle_bets()
