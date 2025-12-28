import requests
import os
import time
import json
from datetime import datetime, timedelta, timezone

# ================= KONFIGURACJA =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")

# Pobieranie kluczy z Secrets
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
TAX_RATE = 0.88         # Podatek 12%
EV_THRESHOLD = 3.0      # Minimalny zysk 3%
BANKROLL = 1000         # Twój budżet
KELLY_FRACTION = 0.2    # Mnożnik stawki (bezpieczny)

# ================= FUNKCJE POMOCNICZE =================

def send_msg(text):
    """Wysyła wiadomość do Telegrama"""
    if not T_TOKEN or not T_CHAT:
        print("BŁĄD: Brak T_TOKEN lub T_CHAT!")
        return
    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
    payload = {"chat_id": T_CHAT, "text": text, "parse_mode": "Markdown"}
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code == 200:
            print("Powiadomienie wysłane pomyślnie.")
        else:
            print(f"Błąd Telegrama: {r.text}")
    except Exception as e:
        print(f"Wyjątek przy wysyłce: {e}")

def load_state():
    if not os.path.exists(STATE_FILE): return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except: return {}

def save_state(state):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=4)
    except Exception as e:
        print(f"Błąd zapisu stanu: {e}")

def get_fair_odds(odds_list):
    """Oblicza sprawiedliwe kursy (bez marży)"""
    probs = [1/h for h in odds_list]
    total_prob = sum(probs)
    return [1 / (p / total_prob) for p in probs]

# ================= LOGIKA GŁÓWNA =================

def run():
    state = load_state()
    now = datetime.now(timezone.utc)
    
    # Czyszczenie starych meczów (starsze niż 3 dni)
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
                
                rem = r.headers.get('x-requests-remaining')
                print(f"[{sport_label}] Klucz: {key[:5]}... Pozostało: {rem}")

                if r.status_code == 200:
                    matches = r.json()
                    break
                elif r.status_code == 429: continue 
            except: continue
        
        if not matches: continue

        for match in matches:
            m_id = match["id"]
            if f"{m_id}_v" in state: continue # Pomiń wysłane
            
            home = match["home_team"]
            away = match["away_team"]
            
            all_odds = {"h": [], "d": [], "a": []}
            for bm in match.get("bookmakers", []):
                for market in bm.get("markets", []):
                    if market["key"] == "h2h":
                        outcomes = {o["name"]: o["price"] for o in market["outcomes"]}
                        if home in outcomes and away in outcomes:
                            all_odds["h"].append(outcomes[home])
                            all_odds["a"].append(outcomes[away])
                            if "Draw" in outcomes:
                                all_odds["d"].append(outcomes["Draw"])

            # Wymagane min. 3 bukmacherów dla wiarygodności
            if len(all_odds["h"]) < 3: continue

            avg_h = sum(all_odds["h"]) / len(all_odds["h"])
            avg_a = sum(all_odds["a"]) / len(all_odds["a"])
            
            if all_odds["d"]: # Piłka nożna
                avg_d = sum(all_odds["d"]) / len(all_odds["d"])
                fair_h, fair_d, fair_a = get_fair_odds([avg_h, avg_d, avg_a])
            else: # NBA/NHL
                fair_h, fair_a = get_fair_odds([avg_h, avg_a])

            max_h, max_a = max(all_odds["h"]), max(all_odds["a"])
            
            # EV z uwzględnieniem podatku
            ev_h = (max_h * TAX_RATE / fair_h - 1) * 100
            ev_a = (max_a * TAX_RATE / fair_a - 1) * 100

            if ev_h >= EV_THRESHOLD or ev_a >= EV_THRESHOLD:
                # Wybór typu z wyższym EV
                pick, odd, fair, ev = (home, max_h, fair_h, ev_h) if ev_h > ev_a else (away, max_a, fair_a, ev_a)
                
                # Obliczanie stawki Kelly'ego
                p = 1 / fair
                b = (odd * TAX_RATE) - 1
                if b > 0:
                    kelly = ((b * p - (1 - p)) / b) * KELLY_FRACTION
                    stake = max(0, round(BANKROLL * kelly, 2))
                    
                    if stake > 2: 
                        msg = (
                            f"💎 **VALUE (+EV)**\n"
                            f"🏆 {sport_label}\n"
                            f"⚔️ **{home} vs {away}**\n"
                            f"━━━━━━━━━━━━━━━\n"
                            f"✅ TYP: *{pick}*\n"
                            f"📈 Kurs: `{odd:.2f}` (Fair: {fair:.2f})\n"
                            f"🔥 EV: `+{ev:.1f}%`\n"
                            f"💰 Stawka: *{stake} zł*"
                        )
                        print(f"Znaleziono okazję: {pick}")
                        send_msg(msg)
                        
                        state[f"{m_id}_v"] = {"time": now.isoformat(), "pick": pick}
                        save_state(state)

if __name__ == "__main__":
    current_time = datetime.now().strftime("%H:%M:%S")
    print(f"Start bota o {current_time}")
    # Opcjonalnie: send_msg(f"🤖 Bot wystartował o {current_time}") 
    run()
