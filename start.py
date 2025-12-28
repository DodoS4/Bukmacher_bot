import requests
import os
import time
import json
from datetime import datetime, timedelta, timezone

# ================= KONFIGURACJA =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")

KEYS_POOL = [os.getenv("ODDS_KEY"), os.getenv("ODDS_KEY_2"), os.getenv("ODDS_KEY_3")]
API_KEYS = [k for k in KEYS_POOL if k]

SPORTS_CONFIG = {
    "soccer_epl": "⚽ PREMIER LEAGUE",
    "soccer_spain_la_liga": "⚽ LA LIGA",
    "soccer_germany_bundesliga": "⚽ BUNDESLIGA",
    "soccer_italy_serie_a": "⚽ SERIE A",
    "soccer_poland_ekstraklasa": "⚽ EKSTRAKLASA",
    "basketball_nba": "🏀 NBA",
    "icehockey_nhl": "🏒 NHL",
}

STATE_FILE = "sent.json"
TAX_RATE = 0.88         
EV_THRESHOLD = 3.0      
BANKROLL = 1000         
KELLY_FRACTION = 0.2    

# ================= FUNKCJE POMOCNICZE =================

def load_state():
    if not os.path.exists(STATE_FILE): return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except: return {}

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=4)

def get_fair_odds(odds_list):
    """Oblicza sprawiedliwe kursy usuwając marżę (działa dla 2 i 3 wyników)"""
    probs = [1/h for h in odds_list]
    total_prob = sum(probs)
    return [1 / (p / total_prob) for p in probs]

# ================= LOGIKA POBIERANIA =================

def run():
    state = load_state()
    now = datetime.now(timezone.utc)
    
    # Filtracja starych wpisów
    state = {k: v for k, v in state.items() if (now - datetime.fromisoformat(v['time'] if isinstance(v, dict) else v)).days < 3}

    for sport_key, sport_label in SPORTS_CONFIG.items():
        matches = None
        for key in API_KEYS:
            try:
                r = requests.get(
                    f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/",
                    params={"apiKey": key, "regions": "eu", "markets": "h2h"},
                    timeout=15
                )
                
                # Logowanie limitu
                rem = r.headers.get('x-requests-remaining')
                print(f"[{sport_label}] Klucz: {key[:5]}... Pozostało: {rem}")

                if r.status_code == 200:
                    matches = r.json()
                    break
                elif r.status_code == 429: continue # Limit klucza, sprawdź następny
            except: continue
        
        if not matches: continue

        for match in matches:
            m_id = match["id"]
            if f"{m_id}_v" in state: continue
            
            home = match["home_team"]
            away = match["away_team"]
            
            # Pobieranie kursów od wszystkich bukmacherów
            all_odds = {"h": [], "d": [], "a": []}
            for bm in match.get("bookmakers", []):
                for market in bm.get("markets", []):
                    if market["key"] == "h2h":
                        outcomes = {o["name"]: o["price"] for o in market["outcomes"]}
                        if home in outcomes and away in outcomes:
                            all_odds["h"].append(outcomes[home])
                            all_odds["a"].append(outcomes[away])
                            if "Draw" in outcomes: all_odds["d"].append(outcomes["Draw"])

            # Minimum 3 bukmacherów do analizy średniej
            if len(all_odds["h"]) < 3: continue

            # Średnie i Fair Odds
            avg_h = sum(all_odds["h"]) / len(all_odds["h"])
            avg_a = sum(all_odds["a"]) / len(all_odds["a"])
            
            if all_odds["d"]: # Piłka nożna (1X2)
                avg_d = sum(all_odds["d"]) / len(all_odds["d"])
                fair_h, fair_d, fair_a = get_fair_odds([avg_h, avg_d, avg_a])
            else: # NBA / NHL (12)
                fair_h, fair_a = get_fair_odds([avg_h, avg_a])

            # Szukanie Value (porównanie najlepszego kursu z fair odds)
            max_h, max_a = max(all_odds["h"]), max(all_odds["a"])
            
            # Sprawdzenie EV dla Home i Away (uwzględniając podatek)
            ev_h = (max_h * TAX_RATE / fair_h - 1) * 100
            ev_a = (max_a * TAX_RATE / fair_a - 1) * 100

            if ev_h >= EV_THRESHOLD or ev_a >= EV_THRESHOLD:
                # Wybór lepszego value
                pick, odd, fair, ev = (home, max_h, fair_h, ev_h) if ev_h > ev_a else (away, max_a, fair_a, ev_a)
                
                # Kelly Stake
                p = 1 / fair
                b = (odd * TAX_RATE) - 1
                if b > 0:
                    kelly = ((b * p - (1 - p)) / b) * KELLY_FRACTION
                    stake = max(0, round(BANKROLL * kelly, 2))
                    
                    if stake > 5: # Wysyłaj tylko jeśli stawka ma sens
                        msg = f"💎 **VALUE (+EV)**\n🏆 {sport_label}\n⚔️ {home} vs {away}\n✅ Typ: *{pick}*\n📈 Kurs: `{odd:.2f}` (Fair: {fair:.2f})\n🔥 EV: `+{ev:.1f}%`\n💰 Stawka: *{stake} zł*"
                        print(f"Znaleziono: {pick} @ {odd}")
                        # Tu funkcja send_msg(msg) - użyj swojej
                        state[f"{m_id}_v"] = {"time": now.isoformat(), "pick": pick}
                        save_state(state)

if __name__ == "__main__":
    run()
