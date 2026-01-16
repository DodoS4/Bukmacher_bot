import os
import json
import requests
from datetime import datetime, timezone

# Konfiguracja (Pobierana z GitHub Secrets)
COUPON_FILE = "coupons.json"
RESULTS_FILE = "history.json"  # Zmieniono nazwę na history, by podkreślić archiwizację
BANKROLL_FILE = "bankroll.json"
TELEGRAM_TOKEN = os.getenv("T_TOKEN")
TELEGRAM_CHAT = os.getenv("T_CHAT_RESULTS") # Osobny kanał na wyniki jest dobrą praktyką
API_KEY = os.getenv("ODDS_KEY")

STAKE_PERCENT = 0.02 

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": TELEGRAM_CHAT, "text": message, "parse_mode": "HTML"})

def load_json(filename, default_value):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default_value

def get_real_results(sport_key):
    """Pobiera realne wyniki z API dla dyscypliny"""
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/scores/?apiKey={API_KEY}&daysFrom=3"
    try:
        resp = requests.get(url)
        return resp.json() if resp.status_code == 200 else []
    except:
        return []

def settle_coupons():
    coupons = load_json(COUPON_FILE, [])
    history = load_json(RESULTS_FILE, [])
    br_data = load_json(BANKROLL_FILE, {"bankroll": 1000})
    
    bankroll = br_data["bankroll"]
    still_active = []
    new_results_count = 0

    # Cache wyników, żeby nie pytać API 100 razy o ten sam sport
    scores_cache = {}

    for c in coupons:
        match_time = datetime.fromisoformat(c["time"].replace("Z", "+00:00"))
        
        # Jeśli mecz jeszcze trwa lub się nie zaczął - zostawiamy w aktywnych
        if match_time > datetime.now(timezone.utc):
            still_active.append(c)
            continue

        # Pobieramy wyniki dla ligi (jeśli jeszcze nie ma w cache)
        sport = c.get("sport_key", "soccer_epl") # upewnij się, że start.py zapisuje sport_key
        if sport not in scores_cache:
            scores_cache[sport] = get_real_results(sport)

        # Szukamy konkretnego meczu w wynikach API
        match_data = next((m for m in scores_cache[sport] if m["home_team"] == c["home"]), None)

        if match_data and match_data.get("completed"):
            # LOGIKA ROZSTRZYGNIĘCIA (Uproszczona dla H2H)
            # score: [{"name": "Team A", "score": "2"}, {"name": "Team B", "score": "1"}]
            home_score = int(next(s["score"] for s in match_data["scores"] if s["name"] == c["home"]))
            away_score = int(next(s["score"] for s in match_data["scores"] if s["name"] == c["away"]))
            
            winner = "Draw"
            if home_score > away_score: winner = c["home"]
            elif away_score > home_score: winner = c["away"]

            is_win = (c["pick"] == winner)
            stake = bankroll * STAKE_PERCENT
            profit = stake * (c["odds"] - 1) if is_win else -stake
            bankroll += profit

            status_icon = "✅" if is_win else "❌"
            result_entry = {
                "match": f"{c['home']} vs {c['away']}",
                "pick": c["pick"],
                "score": f"{home_score}:{away_score}",
                "profit": round(profit, 2),
                "date": c["time"]
            }
            
            history.append(result_entry)
            new_results_count += 1
            
            send_telegram(
                f"{status_icon} <b>Wynik: {match_data['home_team']} {home_score}:{away_score} {match_data['away_team']}</b>\n"
                f"🎯 Typ: {c['pick']} (@{c['odds']})\n"
                f"💰 Zysk: {profit:.2f} PLN"
            )
        else:
            # Mecz się zaczął, ale API jeszcze nie ma wyniku "completed"
            still_active.append(c)

    # Zapisujemy stan
    with open(COUPON_FILE, "w", encoding="utf-8") as f:
        json.dump(still_active, f, indent=4)
    
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=4)
        
    with open(BANKROLL_FILE, "w", encoding="utf-8") as f:
        json.dump({"bankroll": round(bankroll, 2)}, f, indent=4)

    print(f"[INFO] Rozliczono: {new_results_count} | Aktywne: {len(still_active)}")

if __name__ == "__main__":
    settle_coupons()
