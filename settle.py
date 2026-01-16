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

STAKE_PERCENT = 0.02  # 2% bankrolla na jeden typ

# Listy sportów dla logiki rozliczania
USA_SPORTS = ["basketball_nba", "icehockey_nhl", "americanfootball_nfl", "baseball_mlb"]

def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT, "text": message, "parse_mode": "HTML", "disable_web_page_preview": True})
    except Exception as e:
        print(f"Błąd wysyłki Telegram: {e}")

def load_json(filename, default):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            try: return json.load(f)
            except: return default
    return default

def get_results(sport_key):
    """Pobiera wyniki z The-Odds-API (do 3 dni wstecz)"""
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/scores/?apiKey={API_KEY}&daysFrom=3"
    try:
        resp = requests.get(url, timeout=15)
        return resp.json() if resp.status_code == 200 else []
    except:
        return []

def get_score_by_team(scores, team_name):
    """Bezpieczne pobieranie wyniku - odporne na drobne różnice w nazwach"""
    for s in scores:
        if s["name"].lower() in team_name.lower() or team_name.lower() in s["name"].lower():
            return int(s["score"])
    return None

def determine_winner(h_score, a_score, home_team, away_team, sport_key):
    """Logika wyłaniania zwycięzcy zależna od dyscypliny"""
    if sport_key in USA_SPORTS:
        # W NBA/NHL nie ma remisów w zakładach H2H (wliczana dogrywka)
        return home_team if h_score > a_score else away_team
    
    # Piłka nożna (Rynek 1X2)
    if h_score > a_score: return home_team
    elif a_score > h_score: return away_team
    else: return "Draw"

def settle():
    coupons = load_json(COUPON_FILE, [])
    history = load_json(HISTORY_FILE, [])
    br_data = load_json(BANKROLL_FILE, {"bankroll": 1000.0})
    
    bankroll = br_data["bankroll"]
    still_active = []
    scores_cache = {}
    new_settled = 0

    print(f"Rozpoczynam rozliczanie... Aktualny BR: {bankroll:.2f} PLN")

    for c in coupons:
        # 1. Sprawdzenie czasu (czy mecz już się zaczął/skończył)
        match_time = datetime.fromisoformat(c["time"].replace("Z", "+00:00"))
        if match_time > datetime.now(timezone.utc):
            still_active.append(c)
            continue

        # 2. Pobieranie wyników (z cache)
        sport = c.get("sport_key")
        if sport not in scores_cache:
            print(f"Pobieram wyniki dla: {sport}...")
            scores_cache[sport] = get_results(sport)

        # 3. Szukanie meczu w wynikach
        match_data = next((m for m in scores_cache[sport] if m["id"] == c["id"]), None)

        if match_data and match_data.get("completed"):
            scores = match_data.get("scores")
            if not scores:
                still_active.append(c)
                continue

            h_score = get_score_by_team(scores, c["home"])
            a_score = get_score_by_team(scores, c["away"])

            if h_score is None or a_score is None:
                print(f"Błąd dopasowania nazw drużyn dla ID: {c['id']}")
                still_active.append(c)
                continue

            # 4. Ustalenie wyniku i obliczenie profitu
            winner = determine_winner(h_score, a_score, c["home"], c["away"], sport)
            is_win = (c["pick"] == winner)
            
            stake = round(bankroll * STAKE_PERCENT, 2)
            profit = round(stake * (c["odds"] - 1), 2) if is_win else -stake
            bankroll += profit

            # 5. Powiadomienie
            status = "✅ <b>WYGRANA!</b>" if is_win else "❌ <b>PRZEGRANA</b>"
            icon = "💰" if is_win else "📉"
            
            msg = (
                f"{status}\n"
                f"━━━━━━━━━━━━━━━\n"
                f"🏟 <b>{c['home']} vs {c['away']}</b>\n"
                f"🔢 Wynik: <b>{h_score}:{a_score}</b>\n\n"
                f"🎯 Typ: <b>{c['pick']}</b> (@{c['odds']:.2f})\n"
                f"{icon} Zysk/Strata: <b>{profit:+.2f} PLN</b>\n"
                f"💵 Nowy Bankroll: <b>{bankroll:.2f} PLN</b>\n"
                f"━━━━━━━━━━━━━━━"
            )
            send_telegram(msg)

            # 6. Archiwizacja
            history.append({
                "date": c["time"],
                "match": f"{c['home']} vs {c['away']}",
                "sport": c["sport"],
                "profit": profit,
                "win": is_win,
                "odds": c["odds"]
            })
            new_settled += 1
        else:
            # Mecz w trakcie lub brak jeszcze wyników w API
            still_active.append(c)

    # Zapis stanu do plików
    with open(COUPON_FILE, "w", encoding="utf-8") as f:
        json.dump(still_active, f, indent=4, ensure_ascii=False)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=4, ensure_ascii=False)
    with open(BANKROLL_FILE, "w", encoding="utf-8") as f:
        json.dump({"bankroll": round(bankroll, 2)}, f, indent=4, ensure_ascii=False)

    print(f"Zakończono. Rozliczono: {new_settled}, Pozostało aktywnych: {len(still_active)}")

if __name__ == "__main__":
    settle()
