import requests
import os
import json
from datetime import datetime, timedelta, timezone

# ================= KONFIGURACJA DLA STABILNEGO ZYSKU =================

T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")

KEYS_POOL = [
    os.getenv("ODDS_KEY"),
    os.getenv("ODDS_KEY_2"),
    os.getenv("ODDS_KEY_3"),
]
API_KEYS = [k for k in KEYS_POOL if k]

# Skupiamy się na głównych ligach (bardziej przewidywalne kursy)
SPORTS_CONFIG = {
    "soccer_epl": "⚽ PREMIER LEAGUE",
    "soccer_spain_la_liga": "⚽ LA LIGA",
    "soccer_germany_bundesliga": "⚽ BUNDESLIGA",
    "soccer_italy_serie_a": "⚽ SERIE A",
    "soccer_france_ligue_1": "⚽ LIGUE 1",
    "basketball_nba": "🏀 NBA",
    "icehockey_nhl": "🏒 NHL",
}

STATE_FILE = "sent.json"

# --- KLUCZOWE PARAMETRY ---
EV_THRESHOLD = 5.5      # Minimum 5.5% przewagi (po uwzględnieniu podatku)
MIN_ODD = 1.70          # Dolna granica stabilności
MAX_ODD = 3.00          # GÓRNA GRANICA - redukcja serii porażek
MIN_BOOKS = 8           # Wymagamy minimum 8 bukmacherów dla precyzji fair odds
TAX_RATE = 0.88         # Polski podatek (12%)

BANKROLL = 1000         # Twój kapitał początkowy
KELLY_FRACTION = 0.1    # 1/10 Kelly (bardzo bezpieczne stawkowanie)
MAX_STAKE_PCT = 0.02    # Maksymalnie 2% bankrolla na zakład (20 zł)

# ================= NARZĘDZIA =================

def send_msg(text):
    if not T_TOKEN or not T_CHAT:
        print(text) # Jeśli brak Telegrama, wypisz w konsoli
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
            json={"chat_id": T_CHAT, "text": text, "parse_mode": "Markdown"},
            timeout=10
        )
    except:
        pass

def trimmed_mean(data, trim=0.2):
    """Oblicza średnią odrzucając skrajne wartości (anty-ghost odds)"""
    data = sorted(data)
    k = int(len(data) * trim)
    if len(data) - 2 * k <= 0:
        return sum(data) / len(data)
    return sum(data[k:-k]) / len(data[k:-k])

def get_fair_odds(odds_list):
    """Usuwa marżę bukmacherską"""
    probs = [1 / o for o in odds_list]
    total_prob = sum(probs)
    return [1 / (p / total_prob) for p in probs]

def load_state():
    if not os.path.exists(STATE_FILE): return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f: return json.load(f)
    except: return {}

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

# ================= GŁÓWNA LOGIKA =================

def run():
    state = load_state()
    now = datetime.now(timezone.utc)
    
    # Czyszczenie starych meczów
    state = {k: v for k, v in state.items() if (now - datetime.fromisoformat(v["time"])).days < 2}

    for sport_key, sport_label in SPORTS_CONFIG.items():
        matches = None
        for key in API_KEYS:
            try:
                r = requests.get(
                    f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/",
                    params={"apiKey": key, "regions": "eu", "markets": "h2h"},
                    timeout=15
                )
                if r.status_code == 200:
                    matches = r.json()
                    break
            except: continue

        if not matches: continue

        for match in matches:
            try:
                match_id = match["id"]
                if match_id in state: continue

                home = match["home_team"]
                away = match["away_team"]
                start = datetime.fromisoformat(match["commence_time"].replace("Z", "+00:00"))

                # Analizujemy tylko mecze w ciągu najbliższych 48h
                if start < now or start > now + timedelta(hours=48): continue

                odds = {"h": [], "a": [], "d": []}
                for bm in match.get("bookmakers", []):
                    for market in bm.get("markets", []):
                        if market["key"] != "h2h": continue
                        prices = {o["name"]: o["price"] for o in market["outcomes"]}
                        if home in prices and away in prices:
                            odds["h"].append(prices[home])
                            odds["a"].append(prices[away])
                            if "Draw" in prices: odds["d"].append(prices["Draw"])

                # WYMAGANIA DOTYCZĄCE DANYCH
                if len(odds["h"]) < MIN_BOOKS: continue

                avg_h = trimmed_mean(odds["h"])
                avg_a = trimmed_mean(odds["a"])
                
                if odds["d"]:
                    avg_d = trimmed_mean(odds["d"])
                    fair_h, fair_d, fair_a = get_fair_odds([avg_h, avg_d, avg_a])
                else:
                    fair_h, fair_a = get_fair_odds([avg_h, avg_a])

                max_h = max(odds["h"])
                max_a = max(odds["a"])

                # Filtr "Ghost Odds" (zabezpieczenie przed błędami API)
                if max_h > avg_h * 1.20 or max_a > avg_a * 1.20: continue

                # Obliczamy EV uwzględniając podatek
                ev_h = (max_h * TAX_RATE / fair_h - 1) * 100
                ev_a = (max_a * TAX_RATE / fair_a - 1) * 100

                # Wybieramy najlepszy typ
                pick, odd, fair, ev = (
                    (home, max_h, fair_h, ev_h) if ev_h > ev_a else (away, max_a, fair_a, ev_a)
                )

                # KLUCZOWE FILTRY
                if ev < EV_THRESHOLD: continue
                if not (MIN_ODD <= odd <= MAX_ODD): continue

                # OBLICZANIE STAWKI (Kelly Criterion 1/10)
                p = 1 / fair
                b = odd * TAX_RATE - 1
                if b <= 0: continue
                
                kelly = ((b * p - (1 - p)) / b) * KELLY_FRACTION
                stake = min(BANKROLL * kelly, BANKROLL * MAX_STAKE_PCT)
                stake = round(stake, 2)

                if stake < 2: continue # Nie wysyłaj zbyt małych stawek

                msg = (
                    f"💰 **NOWA OKAZJA +EV**\n"
                    f"🏆 {sport_label}\n"
                    f"⚔️ **{home} vs {away}**\n"
                    f"━━━━━━━━━━━━━━━\n"
                    f"✅ TYP: *{pick}*\n"
                    f"📈 Kurs: `{odd:.2f}` (Fair: {fair:.2f})\n"
                    f"🔥 EV: `+{ev:.1f}%` (po podatku)\n"
                    f"💵 Stawka: *{stake} zł*\n"
                    f"━━━━━━━━━━━━━━━"
                )

                send_msg(msg)
                state[match_id] = {"time": now.isoformat(), "pick": pick}
                save_state(state)

            except Exception as e:
                print(f"Błąd przetwarzania meczu: {e}")

if __name__ == "__main__":
    run()
