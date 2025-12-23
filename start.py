import requests
import os
import time
from datetime import datetime, timedelta, timezone

# --- KONFIGURACJA ---
T_TOKEN = os.getenv('T_TOKEN')
T_CHAT = os.getenv('T_CHAT')
ODDS_KEY = os.getenv('ODDS_KEY')

SPORTS_CONFIG = {
    'soccer_epl': '⚽ PREMIER LEAGUE',
    'soccer_spain_la_liga': '⚽ LA LIGA',
    'soccer_germany_bundesliga': '⚽ BUNDESLIGA',
    'basketball_nba': '🏀 NBA',
    'icehockey_nhl': '🏒 NHL',
    'mma_mixed_martial_arts': '🥊 MMA/UFC'
}

DB_FILE = "sent_matches.txt"

# PROGI KURSOWE
LIMIT_PEWNIAK = 1.35
LIMIT_WARTE_UWAGI = 1.70

def send_msg(txt):
    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
    payload = {'chat_id': T_CHAT, 'text': txt, 'parse_mode': 'Markdown'}
    try:
        requests.post(url, json=payload, timeout=10)
    except:
        pass

def is_already_sent(match_id):
    if not os.path.exists(DB_FILE): return False
    with open(DB_FILE, "r") as f:
        return str(match_id) in f.read().splitlines()

def mark_as_sent(match_id):
    with open(DB_FILE, "a") as f:
        f.write(str(match_id) + "\n")

def run_radar():
    if not ODDS_KEY: return
    
    now = datetime.now(timezone.utc)
    future_window = now + timedelta(days=7)

    for sport_key, sport_label in SPORTS_CONFIG.items():
        try:
            url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/?apiKey={ODDS_KEY}&regions=eu&markets=h2h"
            res = requests.get(url, timeout=10).json()

            for match in res:
                m_id = match['id']
                m_dt = datetime.strptime(match['commence_time'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)

                if now < m_dt < future_window and not is_already_sent(m_id):
                    home = match['home_team']
                    away = match['away_team']
                    
                    try:
                        outcomes = match['bookmakers'][0]['markets'][0]['outcomes']
                        o_h = next(o['price'] for o in outcomes if o['name'] == home)
                        o_a = next(o['price'] for o in outcomes if o['name'] == away)
                        min_odds = min(o_h, o_a)
                        
                        # LOGIKA KATEGORII
                        tag = ""
                        if min_odds <= LIMIT_PEWNIAK:
                            tag = "🔥 *PEWNIAK: WYSOKA SZANSA* 🔥\n"
                        elif min_odds <= LIMIT_WARTE_UWAGI:
                            tag = "⭐ *WARTE UWAGI: WYRAŹNY FAWORYT* ⭐\n"
                        else:
                            # Jeśli kursy są wyrównane, pomijamy lub wysyłamy jako zwykły mecz
                            tag = "📅 *NADCHODZĄCY MECZ*\n"

                        msg = (f"{tag}"
                               f"🏆 {sport_label}\n"
                               f"⚔️ *{home}* vs *{away}*\n"
                               f"📊 Kursy: `1: {o_h}` | `2: {o_a}`\n"
                               f"⏰ `{m_dt.strftime('%d.%m o %H:%M')}` UTC")

                        send_msg(msg)
                        mark_as_sent(m_id)
                        time.sleep(1)
                    except:
                        continue
            time.sleep(1)
        except:
            continue

if __name__ == "__main__":
    run_radar()
