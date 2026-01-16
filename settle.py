import os
import json
import requests
from datetime import datetime, timezone

# Konfiguracja
COUPON_FILE = "coupons.json"
HISTORY_FILE = "history.json"
BANKROLL_FILE = "bankroll.json"
TELEGRAM_TOKEN = os.getenv("T_TOKEN")
TELEGRAM_CHAT = os.getenv("T_CHAT_RESULTS")  # Wyniki na osobny kanał lub ten sam
API_KEY = os.getenv("ODDS_KEY")

STAKE_PERCENT = 0.02  # 2% bankrolla na jeden typ

def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT, "text": message, "parse_mode": "HTML"})
    except:
        pass

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
        resp = requests.get(url)
        return resp.json() if resp.status_code == 200 else []
    except:
        return []

def settle():
    coupons = load_json(COUPON_FILE, [])
    history = load_json(HISTORY_FILE, [])
    br_data = load_json(BANKROLL_FILE, {"bankroll": 1000.0})
    
    bankroll = br_data["bankroll"]
    still_active = []
    scores_cache = {}
    new_settled = 0

    for c in coupons:
        # Sprawdzamy czy czas meczu już minął (z marginesem 2h na trwanie meczu)
        match_time = datetime.fromisoformat(c["time"].replace("Z", "+00:00"))
        if match_time > datetime.now(timezone.utc):
            still_active.append(c)
            continue

        # Pobieramy wyniki dla ligi jeśli jeszcze ich nie mamy w tym przebiegu
        sport = c.get("sport_key")
        if sport not in scores_cache:
            scores_cache[sport] = get_results(sport)

        # Szukamy konkretnego meczu po ID
        match_data = next((m for m in scores_cache[sport] if m["id"] == c["id"]), None)

        if match_data and match_data.get("completed"):
            scores = match_data["scores"]
            try:
                h_score = int(next(s["score"] for s in scores if s["name"] == c["home"]))
                a_score = int(next(s["score"] for s in scores if s["name"] == c["away"]))
                
                winner = "Draw"
                if h_score > a_score: winner = c["home"]
                elif a_score > h_score: winner = c["away"]

                is_win = (c["pick"] == winner)
                stake = round(bankroll * STAKE_PERCENT, 2)
                profit = round(stake * (c["odds"] - 1), 2) if is_win else -stake
                bankroll += profit

                # --- ELEGANCKIE POWIADOMIENIE ---
                status = "✅ <b>WYGRANA!</b>" if is_win else "❌ <b>PRZEGRANA</b>"
                icon = "💰" if is_win else "📉"
                
                msg = (
                    f"{status}\n"
                    f"━━━━━━━━━━━━━━━\n"
                    f"🏟 <b>{c['home']} vs {c['away']}</b>\n"
                    f"🔢 Wynik: <b>{h_score}:{a_score}</b>\n\n"
                    f"🎯 Twój typ: {c['pick']} (@{c['odds']})\n"
                    f"{icon} Zysk/Strata: <b>{profit:+.2f} PLN</b>\n"
                    f"💵 Nowy BR: <b>{bankroll:.2f} PLN</b>\n"
                    f"━━━━━━━━━━━━━━━"
                )
                send_telegram(msg)

                # Zapis do historii dla stats.py
                history.append({
                    "date": c["time"],
                    "match": f"{c['home']} vs {c['away']}",
                    "sport": c["sport"],
                    "profit": profit,
                    "win": is_win
                })
                new_settled += 1
            except Exception as e:
                print(f"Błąd przy rozliczaniu meczu {c['id']}: {e}")
                still_active.append(c)
        else:
            # Mecz się jeszcze nie skończył lub brak wyników w API
            still_active.append(c)

    # Zapis stanu
    with open(COUPON_FILE, "w", encoding="utf-8") as f:
        json.dump(still_active, f, indent=4)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=4)
    with open(BANKROLL_FILE, "w", encoding="utf-8") as f:
        json.dump({"bankroll": round(bankroll, 2)}, f, indent=4)

    print(f"Rozliczono: {new_settled} typów. Aktywne: {len(still_active)}")

if __name__ == "__main__":
    settle()
