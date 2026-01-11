import requests, json, os
from datetime import datetime, timezone

# ================= CONFIG =================
COUPONS_FILE = "coupons.json"
BANKROLL_FILE = "bankroll.json"
API_KEYS = [k for k in [
    os.getenv("ODDS_KEY"), os.getenv("ODDS_KEY_2"), os.getenv("ODDS_KEY_3")
] if k]

def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f: return json.load(f)
        except: pass
    return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f: json.dump(data, f, indent=2)

def settle_bets():
    coupons = load_json(COUPONS_FILE, [])
    bank_data = load_json(BANKROLL_FILE, {"bankroll": 0.0})
    bankroll = bank_data["bankroll"]
    
    pending_coupons = [c for c in coupons if c["status"] == "PENDING"]
    if not pending_coupons:
        print("Brak kuponów do rozliczenia.")
        return

    # Pobieramy unikalne ligi, aby nie pytać API 100 razy o to samo
    leagues_to_check = list(set(c["league"] for c in pending_coupons))
    
    results_map = {} # Klucz: match_id, Wartość: zwycięzca

    for league in leagues_to_check:
        print(f"Sprawdzam wyniki dla: {league}")
        for key in API_KEYS:
            try:
                r = requests.get(
                    f"https://api.the-odds-api.com/v4/sports/{league}/scores/",
                    params={"apiKey": key, "daysFrom": 3}, timeout=15
                )
                if r.status_code != 200: continue
                
                events = r.json()
                for e in events:
                    if e["completed"]:
                        # Szukamy zwycięzcy na podstawie punktów
                        scores = e["scores"]
                        if scores and len(scores) == 2:
                            s1 = int(scores[0]["score"])
                            s2 = int(scores[1]["score"])
                            if s1 > s2: winner = scores[0]["name"]
                            elif s2 > s1: winner = scores[1]["name"]
                            else: winner = "Draw"
                            
                            match_key = f"{e['home_team']}_{e['away_team']}"
                            results_map[match_key] = winner
                break 
            except: continue

    # Rozliczamy kupony na podstawie zebranych wyników
    settled_count = 0
    for c in coupons:
        if c["status"] != "PENDING": continue
        
        match_key = f"{c['home']}_{c['away']}"
        if match_key in results_map:
            winner = results_map[match_key]
            if c["pick"] == winner:
                c["status"] = "WON"
                bankroll += c["possible_win"]
                print(f"✅ WYGRANA: {match_key} (+{c['possible_win']} PLN)")
            else:
                c["status"] = "LOST"
                print(f"❌ PRZEGRANA: {match_key}")
            settled_count += 1

    if settled_count > 0:
        save_json(COUPONS_FILE, coupons)
        save_json(BANKROLL_FILE, {"bankroll": round(bankroll, 2)})
        print(f"Rozliczono {settled_count} zakładów. Nowy stan konta: {round(bankroll, 2)} PLN")
    else:
        print("Nie znaleziono jeszcze wyników dla oczekujących meczów.")

if __name__ == "__main__":
    settle_bets()
