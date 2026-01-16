import os
import json
import requests
from datetime import datetime, timezone

# ================= KONFIGURACJA =================
COUPON_FILE = "coupons.json"
HISTORY_FILE = "history.json"
BANKROLL_FILE = "bankroll.json"
TELEGRAM_TOKEN = os.getenv("T_TOKEN")
TELEGRAM_CHAT = os.getenv("T_CHAT_RESULTS")
API_KEY = os.getenv("ODDS_KEY")

TAX_PL = 0.88 # 12% podatku
USA_SPORTS = ["basketball_nba", "icehockey_nhl", "americanfootball_nfl", "baseball_mlb"]

def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT, "text": message, "parse_mode": "HTML"})
    except: pass

def load_json(filename, default):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            try: return json.load(f)
            except: return default
    return default

def get_results(sport_key):
    # Pobieramy wyniki z ostatnich 3 dni
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/scores/?apiKey={API_KEY}&daysFrom=3"
    try:
        resp = requests.get(url, timeout=15)
        return resp.json() if resp.status_code == 200 else []
    except: return []

def determine_winner(scores, c, sport_key):
    # Wyciąganie punktów
    h_score = next((s["score"] for s in scores if s["name"] == c["home"]), None)
    a_score = next((s["score"] for s in scores if s["name"] == c["away"]), None)
    
    if h_score is None or a_score is None: return None
    
    h_score, a_score = int(h_score), int(a_score)
    
    if h_score > a_score: return c["home"]
    if a_score > h_score: return c["away"]
    return "Draw"

def settle():
    coupons = load_json(COUPON_FILE, [])
    history = load_json(HISTORY_FILE, [])
    br_data = load_json(BANKROLL_FILE, {"bankroll": 10000.0}) # Startujemy z 10k pod cel 5k
    
    bankroll = br_data["bankroll"]
    start_br = bankroll
    still_active = []
    scores_cache = {}
    results_list = []

    for c in coupons:
        # Sprawdzamy czy mecz już się odbył
        match_time = datetime.fromisoformat(c["time"].replace("Z", "+00:00"))
        if match_time > datetime.now(timezone.utc):
            still_active.append(c)
            continue

        sport = c.get("sport_key", "soccer_poland_ekstraklasa") # domyślny klucz
        if sport not in scores_cache:
            scores_cache[sport] = get_results(sport)

        match_data = next((m for m in scores_cache[sport] if m["id"] == c["id"]), None)

        if match_data and match_data.get("completed"):
            winner = determine_winner(match_data.get("scores"), c, sport)
            if winner is None:
                still_active.append(c)
                continue

            is_win = (c["pick"] == winner)
            stake = c.get("stake", 200)
            
            # REALNE ROZLICZENIE Z PODATKIEM 12%
            if is_win:
                # Wygrana netto = (Stawka * 0.88 * Kurs) - Stawka
                profit = round((stake * TAX_PL * c["odds"]) - stake, 2)
            else:
                profit = -stake
            
            bankroll += profit
            status = "✅" if is_win else "❌"
            results_list.append(f"{status} {c['home']} - {c['away']}\n└ Typ: {c['pick']} | <b>{profit:+.2f} PLN</b>")

            history.append({
                "date": c["time"], "match": f"{c['home']} vs {c['away']}",
                "profit": profit, "win": is_win
            })
        else:
            still_active.append(c)

    if results_list:
        daily_profit = bankroll - start_br
        msg = (
            f"📊 <b>RAPORT ZYSKÓW</b>\n"
            f"━━━━━━━━━━━━━━━\n" +
            "\n".join(results_list) +
            f"\n━━━━━━━━━━━━━━━\n"
            f"💰 Wynik sesji: <b>{daily_profit:+.2f} PLN</b>\n"
            f"🏦 Kapitał: <b>{bankroll:.2f} PLN</b>"
        )
        send_telegram(msg)

    # Zapis
    save_data(COUPON_FILE, still_active)
    save_data(HISTORY_FILE, history)
    save_data(BANKROLL_FILE, {"bankroll": round(bankroll, 2)})

def save_data(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

if __name__ == "__main__":
    settle()
