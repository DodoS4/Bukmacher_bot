import requests, json, os
from datetime import datetime, timezone

# ================= CONFIG =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS")
API_KEY = os.getenv("ODDS_KEY") # Settle potrzebuje tylko jednego, głównego klucza
COUPONS_FILE = "coupons.json"

def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f: return json.load(f)
        except: pass
    return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f: json.dump(data, f, indent=2)

def send_msg(txt):
    if not T_TOKEN or not T_CHAT_RESULTS: return
    try: requests.post(f"https://api.telegram.org/bot{T_TOKEN}/sendMessage", json={"chat_id": T_CHAT_RESULTS, "text": txt, "parse_mode": "HTML"})
    except: pass

def fetch_results(sport):
    # Pobieramy wyniki z ostatnich 3 dni
    url = f"https://api.the-odds-api.com/v4/sports/{sport}/scores/"
    params = {"apiKey": API_KEY, "daysFrom": 3}
    r = requests.get(url, params=params)
    if r.status_code == 200: return r.json()
    return []

def settle_coupons():
    coupons = load_json(COUPONS_FILE, [])
    pending = [c for c in coupons if c.get("status") == "PENDING"]
    
    if not pending:
        print("✅ Brak meczów do rozliczenia.")
        return

    # Grupowanie sportów, aby nie pytać API o to samo kilka razy
    sports_to_check = list(set([c["league_key"] for c in pending]))
    all_results = {}
    
    for sport in sports_to_check:
        all_results[sport] = fetch_results(sport)

    changed = False
    for c in coupons:
        if c.get("status") != "PENDING": continue
        
        # Szukamy wyniku dla konkretnego meczu
        match_result = next((r for r in all_results.get(c["league_key"], []) 
                             if r["home_team"] == c["home"] and r["away_team"] == c["away"] and r["completed"]), None)
        
        if match_result:
            # Wyciągamy punkty/bramki
            scores = {s["name"]: int(s["score"]) for s in match_result["scores"]}
            home_score = scores.get(c["home"], 0)
            away_score = scores.get(c["away"], 0)
            
            # Logika wygranej
            is_win = False
            if c["pick"] == c["home"] and home_score > away_score: is_win = True
            if c["pick"] == c["away"] and away_score > home_score: is_win = True
            # W rynkach 2-way (NHL/NBA/Tenis) nie ma remisów, więc to wystarczy

            c["status"] = "WON" if is_win else "LOST"
            c["score"] = f"{home_score}:{away_score}"
            changed = True
            
            # Powiadomienie na Telegram
            icon = "✅" if is_win else "❌"
            profit = round(c['stake'] * (c['odds'] * 0.88 - 1), 2) if is_win else -c['stake']
            
            msg = (f"{icon} <b>ROZLICZONO: {c['league_name']}</b>\n"
                   f"{c['home']} {home_score}:{away_score} {c['away']}\n"
                   f"Twój typ: <b>{c['pick']}</b>\n"
                   f"Wynik finansowy: <b>{profit} zł</b>")
            send_msg(msg)

    if changed:
        save_json(COUPONS_FILE, coupons)
        print("💾 Zaktualizowano statusy meczów.")

if __name__ == "__main__":
    settle_coupons()
