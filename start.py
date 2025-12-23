import requests
import os
import time
from datetime import datetime, timedelta, timezone

# --- KONFIGURACJA ---
T_TOKEN = os.getenv('T_TOKEN')
T_CHAT = os.getenv('T_CHAT')
ODDS_KEY = os.getenv('ODDS_KEY')

# Wybrane ligi do skanowania
SPORTS_CONFIG = {
    'soccer_epl': '⚽ PREMIER LEAGUE',
    'soccer_spain_la_liga': '⚽ LA LIGA',
    'soccer_germany_bundesliga': '⚽ BUNDESLIGA',
    'soccer_italy_serie_a': '⚽ SERIE A',
    'soccer_poland_ekstraklasa': '⚽ EKSTRAKLASA',
    'basketball_nba': '🏀 NBA',
    'icehockey_nhl': '🏒 NHL',
    'mma_mixed_martial_arts': '🥊 MMA/UFC'
}

DB_FILE = "sent_matches.txt"

def send_msg(txt):
    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
    payload = {'chat_id': T_CHAT, 'text': txt, 'parse_mode': 'Markdown'}
    try:
        requests.post(url, json=payload, timeout=10)
    except:
        pass

def is_already_sent(match_id, category=""):
    unique_key = f"{match_id}_{category}"
    if not os.path.exists(DB_FILE): return False
    with open(DB_FILE, "r") as f:
        return unique_key in f.read().splitlines()

def mark_as_sent(match_id, category=""):
    with open(DB_FILE, "a") as f:
        f.write(f"{match_id}_{category}\n")

def run_pro_radar():
    if not ODDS_KEY: 
        print("Brak klucza API!")
        return
        
    now = datetime.now(timezone.utc)
    
    # --- 🟢 STATUS SYSTEMU (ZIELONY KOMUNIKAT) ---
    if now.hour == 0 or os.getenv('GITHUB_EVENT_NAME') == 'workflow_dispatch':
        status_msg = (f"🟢 *STATUS SYSTEMU: AKTYWNY*\n"
                      f"📅 Data: `{now.strftime('%d.%m.%Y')}`\n"
                      f"🤖 Wszystkie moduły pracują poprawnie.\n"
                      f"📡 Skanowanie: {len(SPORTS_CONFIG)} lig w toku...")
        send_msg(status_msg)

    for sport_key, sport_label in SPORTS_CONFIG.items():
        try:
            url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/?apiKey={ODDS_KEY}&regions=eu&markets=h2h"
            response = requests.get(url, timeout=10)
            if response.status_code != 200: continue
            res = response.json()

            for match in res:
                m_id = match['id']
                home = match['home_team']
                away = match['away_team']
                m_dt = datetime.strptime(match['commence_time'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)

                all_h_odds, all_a_odds = [], []
                for bm in match['bookmakers']:
                    for market in bm['markets']:
                        if market['key'] == 'h2h':
                            try:
                                h_o = next(o['price'] for o in market['outcomes'] if o['name'] == home)
                                a_o = next(o['price'] for o in market['outcomes'] if o['name'] == away)
                                all_h_odds.append(h_o)
                                all_a_odds.append(a_o)
                            except: continue

                if not all_h_odds: continue

                avg_h = sum(all_h_odds) / len(all_h_odds)
                avg_a = sum(all_a_odds) / len(all_a_odds)
                max_h = max(all_h_odds)
                max_a = max(all_a_odds)

                # --- LOGIKA WYBORU FAWORYTA ---
                if avg_h < avg_a:
                    faworyt_txt = f"✅ STAWIAJ NA: *{home.upper()}*\n\n🟢 *{home}*: `{avg_h:.2f}`\n⚪ {away}: `{avg_a:.2f}`"
                    min_avg = avg_h
                else:
                    faworyt_txt = f"✅ STAWIAJ NA: *{away.upper()}*\n\n⚪ {home}: `{avg_h:.2f}`\n🟢 *{away}*: `{avg_a:.2f}`"
                    min_avg = avg_a

                # --- 1. STRATEGIA: BUKMACHER ZASPAŁ! (VALUE BET) ---
                if (max_h > avg_h * 1.12 or max_a > avg_a * 1.12) and not is_already_sent(m_id, "value"):
                    target = home if max_h > avg_h * 1.12 else away
                    val_kurs = max_h if max_h > avg_h * 1.12 else max_a
                    avg_kurs = avg_h if max_h > avg_h * 1.12 else avg_a
                    
                    msg = (f"💎 *BUKMACHER ZASPAŁ!* 💎\n"
                           f"🏆 {sport_label}\n"
                           f"
