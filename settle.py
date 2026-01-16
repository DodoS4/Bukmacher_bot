import json
import os
import requests

# Konfiguracja
ODDS_API_KEY = os.getenv("ODDS_KEY")
HISTORY_FILE = "history.json"
COUPONS_FILE = "coupons.json"
BANKROLL_FILE = "bankroll.json"
TELEGRAM_TOKEN = os.getenv("T_TOKEN")
TELEGRAM_CHAT = os.getenv("T_CHAT_RESULTS")

def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": TELEGRAM_CHAT, "text": message, "parse_mode": "HTML"})

def settle_matches():
    if not os.path.exists(COUPONS_FILE): return
    with open(COUPONS_FILE, "r") as f: coupons = json.load(f)
    if not coupons: return

    with open(BANKROLL_FILE, "r") as f: br_data = json.load(f)
    if not os.path.exists(HISTORY_FILE): 
        with open(HISTORY_FILE, "w") as f: json.dump([], f)
    with open(HISTORY_FILE, "r") as f: history = json.load(f)

    remaining_coupons = []
    
    for c in coupons:
        # Pobieranie wyników dla konkretnej ligi
        url = f"https://api.the-odds-api.com/v4/sports/{c['sport']}/scores/?apiKey={ODDS_API_KEY}&daysFrom=3"
        response = requests.get(url).json()
        
        match_result = next((m for m in response if m['id'] == c['id'] and m['completed']), None)
        
        if match_result:
            # Prosta logika rozliczania (zakładamy 1X2)
            scores = match_result['scores']
            home_score = int(next(s['score'] for s in scores if s['name'] == c['home']))
            away_score = int(next(s['score'] for s in scores if s['name'] == c['away']))
            
            is_win = False
            if c['pick'] == c['home'] and home_score > away_score: is_win = True
            elif c['pick'] == c['away'] and away_score > home_score: is_win = True
            elif c['pick'] == "Draw" and home_score == away_score: is_win = True

            profit = (c['stake'] * c['odds'] - c['stake']) if is_win else -c['stake']
            br_data['bankroll'] += profit
            
            # Zapis do historii z kursem!
            history.append({
                "date": c['time'],
                "match": f"{c['home']} vs {c['away']}",
                "sport": c['sport'],
                "profit": round(profit, 2),
                "win": is_win,
                "odds": c['odds']
            })
            
            status = "✅ WYGRANA" if is_win else "❌ PRZEGRANA"
            send_telegram(f"{status}\n{c['home']} - {c['away']}\nWynik: {home_score}:{away_score}\nProfit: {profit:+.2f} PLN")
        else:
            remaining_coupons.append(c)

    with open(COUPONS_FILE, "w") as f: json.dump(remaining_coupons, f)
    with open(HISTORY_FILE, "w") as f: json.dump(history, f)
    with open(BANKROLL_FILE, "w") as f: json.dump(br_data, f)

if __name__ == "__main__":
    settle_matches()
