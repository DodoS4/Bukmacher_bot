import requests
import os
import time
from datetime import datetime, timedelta, timezone

# --- KONFIGURACJA KLUCZY ---
T_TOKEN = os.getenv('T_TOKEN')
T_CHAT = os.getenv('T_CHAT')

# System rotacji kluczy (jeśli masz ich więcej)
KEYS_POOL = [os.getenv('ODDS_KEY_1'), os.getenv('ODDS_KEY_2'), os.getenv('ODDS_KEY')]
KEYS_POOL = [k for k in KEYS_POOL if k]

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

def get_data(sport_key):
    for key in KEYS_POOL:
        url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/?apiKey={key}&regions=eu&markets=h2h"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return r.json()
    return None

def run_radar():
    now = datetime.now(timezone.utc)
    
    # RAPORT PORANNY
    if now.hour == 0 or os.getenv('GITHUB_EVENT_NAME') == 'workflow_dispatch':
        send_msg(f"🟢 *SYSTEM AKTYWNY*\n📅 `{now.strftime('%d.%m.%Y')}`\n✅ Wszystkie analizy działają.")

    for sport_key, sport_label in SPORTS_CONFIG.items():
        data = get_data(sport_key)
        if not data: continue

        for match in data:
            m_id = match['id']
            home = match['home_team']
            away = match['away_team']
            m_dt = datetime.strptime(match['commence_time'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)

            # Pobieranie kursów
            try:
                outcomes = match['bookmakers'][0]['markets'][0]['outcomes']
                o_h = next(o['price'] for o in outcomes if o['name'] == home)
                o_a = next(o['price'] for o in outcomes if o['name'] == away)
            except: continue

            # --- LOGIKA WYBORU (KOGO POSTAWIĆ) ---
            if o_h < o_a:
                faworyt = f"✅ STAWIAJ NA: *{home.upper()}*"
                kursy_widok = f"🟢 *{home}*: `{o_h:.2f}`\n⚪ {away}: `{o_a:.2f}`"
                min_odd = o_h
            else:
                faworyt = f"✅ STAWIAJ NA: *{away.upper()}*"
                kursy_widok = f"⚪ {home}: `{o_h:.2f}`\n🟢 *{away}*: `{o_a:.2f}`"
                min_odd = o_a

            # --- VALUE BET ---
            if not is_already_sent(m_id, "value"):
                # Przykładowa logika błędu bukmachera (jeśli kurs odbiega o 10%)
                if min_odd > 1.80: # Szukamy wyższych kursów z wartością
                   pass # Tu można dodać bardziej złożone liczenie średniej rynkowej

            # --- WYSYŁKA ---
            if min_odd <= 1.75 and not is_already_sent(m_id, "daily"):
                tag = "🔥 *PEWNIAK*" if min_odd <= 1.35 else "⭐ *WARTE UWAGI*"
                sugestia = "\n🛡️ _Sugerowana podpórka (1X/X2)_" if "⚽" in sport_label and min_odd > 1.40 else ""
                
                msg = (f"{tag}\n🏆 {sport_label}\n"
                       f"━━━━━━━━━━━━━━━\n"
                       f"{faworyt}\n\n"
                       f"{kursy_widok}\n"
                       f"━━━━━━━━━━━━━━━\n"
                       f"⏰ `{m_dt.strftime('%d.%m %H:%M')}` UTC{sugestia}")
                
                send_msg(msg)
                mark_as_sent(m_id, "daily")
        
        time.sleep(1)

if __name__ == "__main__":
    run_radar()
