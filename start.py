import requests
import os
import json
from datetime import datetime, timedelta, timezone

# ================= KONFIGURACJA =================

T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")

KEYS_POOL = [
    os.getenv("ODDS_KEY"),
    os.getenv("ODDS_KEY_2"),
    os.getenv("ODDS_KEY_3"),
]
API_KEYS = [k for k in KEYS_POOL if k]

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

# Strategia
EV_THRESHOLD = 3.0
MIN_ODD = 1.55
MIN_BOOKS = 4
TAX_RATE = 0.88

# Bankroll & staking
BANKROLL = 1000
KELLY_FRACTION = 0.2
MAX_STAKE_PCT = 0.03

# ================= NARZĘDZIA =================

def send_msg(text):
    if not T_TOKEN or not T_CHAT:
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
    data = sorted(data)
    k = int(len(data) * trim)
    if len(data) - 2 * k <= 0:
        return sum(data) / len(data)
    return sum(data[k:-k]) / len(data[k:-k])

def get_fair_odds(odds):
    probs = [1 / o for o in odds]
    total = sum(probs)
    return [1 / (p / total) for p in probs]

def load_state():
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

# ================= GŁÓWNA LOGIKA =================

def run():
    state = load_state()
    now = datetime.now(timezone.utc)

    # Czyść stare wpisy (2 dni)
    state = {
        k: v for k, v in state.items()
        if (now - datetime.fromisoformat(v["time"])).days < 2
    }

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
            except:
                continue

        if not matches:
            continue

        for match in matches:
            try:
                match_id = match["id"]
                if match_id in state:
                    continue

                home = match["home_team"]
                away = match["away_team"]
                start = datetime.fromisoformat(
                    match["commence_time"].replace("Z", "+00:00")
                )

                if start < now or start > now + timedelta(hours=48):
                    continue

                odds = {"h": [], "a": [], "d": []}

                for bm in match.get("bookmakers", []):
                    for market in bm.get("markets", []):
                        if market["key"] != "h2h":
                            continue
                        prices = {o["name"]: o["price"] for o in market["outcomes"]}
                        if home in prices and away in prices:
                            odds["h"].append(prices[home])
                            odds["a"].append(prices[away])
                            if "Draw" in prices:
                                odds["d"].append(prices["Draw"])

                if len(odds["h"]) < MIN_BOOKS:
                    continue

                avg_h = trimmed_mean(odds["h"])
                avg_a = trimmed_mean(odds["a"])

                if odds["d"]:
                    avg_d = trimmed_mean(odds["d"])
                    fair_h, fair_d, fair_a = get_fair_odds([avg_h, avg_d, avg_a])
                else:
                    fair_h, fair_a = get_fair_odds([avg_h, avg_a])

                max_h = max(odds["h"])
                max_a = max(odds["a"])

                # Ghost odds filter
                if max_h > avg_h * 1.25 or max_a > avg_a * 1.25:
                    continue

                ev_h = (max_h * TAX_RATE / fair_h - 1) * 100
                ev_a = (max_a * TAX_RATE / fair_a - 1) * 100

                pick, odd, fair, ev = (
                    (home, max_h, fair_h, ev_h)
                    if ev_h > ev_a
                    else (away, max_a, fair_a, ev_a)
                )

                if ev < EV_THRESHOLD or odd < MIN_ODD:
                    continue

                p = 1 / fair
                b = odd * TAX_RATE - 1
                if b <= 0:
                    continue

                kelly = ((b * p - (1 - p)) / b) * KELLY_FRACTION
                stake = BANKROLL * kelly
                stake = min(stake, BANKROLL * MAX_STAKE_PCT)
                stake = round(stake, 2)

                if stake < 5:
                    continue

                msg = (
                    f"💰 **OKAZJA +EV**\n"
                    f"🏆 {sport_label}\n"
                    f"⚔️ **{home} vs {away}**\n"
                    f"━━━━━━━━━━━━━━━\n"
                    f"✅ TYP: *{pick}*\n"
                    f"📈 Kurs: `{odd:.2f}` (fair {fair:.2f})\n"
                    f"🔥 EV: `+{ev:.1f}%`\n"
                    f"💵 Stawka: *{stake} zł*\n"
                    f"━━━━━━━━━━━━━━━"
                )

                send_msg(msg)
                state[match_id] = {"time": now.isoformat(), "pick": pick}
                save_state(state)

            except Exception as e:
                send_msg(f"⚠️ Błąd: `{e}`")

# ================= START =================

if __name__ == "__main__":
    run()