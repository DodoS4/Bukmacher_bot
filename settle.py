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

STAKE_PERCENT = 0.02
USA_SPORTS = ["basketball_nba", "icehockey_nhl", "americanfootball_nfl", "baseball_mlb"]

def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT, "text": message, "parse_mode": "HTML", "disable_web_page_preview": True})
    except: pass

def load_json(filename, default):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            try: return json.load(f)
            except: return default
    return default

def get_results(sport_key):
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/scores/?apiKey={API_KEY}&daysFrom=3"
    try:
        resp = requests.get(url, timeout=15)
        return resp.json() if resp.status_code == 200 else []
    except: return []

def get_score_by_team(scores, team_name):
    for s in scores:
        if s["name"].lower() in team_name.lower() or team_name.lower() in s["name"].lower():
            return int(s["score"])
    return None

def determine_winner(h_score, a_score, home_team, away_team, sport_key):
    if sport_key in USA_SPORTS:
        return home_team if h_score > a_score else away_team
    if h_score > a_score: return home_team
    elif a_score > h_score: return away_team
    else: return "Draw"

def settle():
    coupons = load_json(COUPON_FILE, [])
    history = load_json(HISTORY_FILE, [])
    br_data = load_json(BANKROLL_FILE, {"bankroll": 1000.0})
    
    bankroll = br_data["bankroll"]
    start_br = bankroll
    still_active = []
    scores_cache = {}
    new_settled = 0
    results_list = []

    for c in coupons:
        match_time = datetime.fromisoformat(c["time"].replace("Z", "+00:00"))
        if match_time > datetime.now(timezone.utc):
            still_active.append(c)
            continue

        sport = c.get("sport_key")
        if sport not in scores_cache:
            scores_cache[sport] = get_results(sport)

        match_data = next((m for m in scores_cache[sport] if m["id"] == c["id"]), None)

        if match_data and match_data.get("completed"):
            scores = match_data.get("scores")
            h_score = get_score_by_team(scores, c["home"])
            a_score = get_score_by_team(scores, c["away"])

            if h_score is None or a_score is None:
                still_active.append(c)
                continue

            winner = determine_winner(h_score, a_score, c["home"], c["away"], sport)
            is_win = (c["pick"] == winner)
            
            stake = round(bankroll * STAKE_PERCENT, 2)
            profit = round(stake * (c["odds"] - 1), 2) if is_win else -stake
            bankroll += profit

            # Dodaj do listy raportu
            status = "✅" if is_win else "❌"
            results_list.append(f"{status} {c['home']} vs {c['away']} ({c['pick']}) | <b>{profit:+.2f} PLN</b>")

            history.append({
                "date": c["time"], "match": f"{c['home']} vs {c['away']}",
                "sport": c["sport"], "profit": profit, "win": is_win, "odds": c["odds"]
            })
            new_settled += 1
        else:
            still_active.append(c)

    # WYSYŁKA RAPORTU
    if new_settled > 0:
        daily_profit = bankroll - start_br
        msg = (
            f"📝 <b>DZIENNY RAPORT WYNIKÓW</b>\n"
            f"━━━━━━━━━━━━━━━\n" +
            "\n".join(results_list) +
            f"\n━━━━━━━━━━━━━━━\n"
            f"💰 Wynik dnia: <b>{daily_profit:+.2f} PLN</b>\n"
            f"🏦 Stan konta: <b>{bankroll:.2f} PLN</b>"
        )
        send_telegram(msg)

    with open(COUPON_FILE, "w", encoding="utf-8") as f:
        json.dump(still_active, f, indent=4)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=4)
    with open(BANKROLL_FILE, "w", encoding="utf-8") as f:
        json.dump({"bankroll": round(bankroll, 2)}, f, indent=4)

if __name__ == "__main__":
    settle()
