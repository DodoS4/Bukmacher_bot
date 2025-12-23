import requests
import os
from datetime import datetime, timedelta, timezone

# --- KONFIGURACJA ---
T_TOKEN = os.getenv('T_TOKEN')
T_CHAT = os.getenv('T_CHAT')
API_KEYS = [os.getenv('ODDS_KEY'), os.getenv('ODDS_KEY_2'), os.getenv('ODDS_KEY_3')]
API_KEYS = [k for k in API_KEYS if k]

DB_FILE = "sent_matches.txt"
HISTORY_FILE = "history.txt"

def send_msg(txt):
    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
    payload = {'chat_id': T_CHAT, 'text': txt, 'parse_mode': 'Markdown'}
    try:
        r = requests.post(url, json=payload, timeout=10)
        return r.status_code == 200
    except:
        return False

def is_already_sent(m_id, cat=""):
    key = f"{m_id}_{cat}"
    if not os.path.exists(DB_FILE):
        return False
    with open(DB_FILE, "r") as f:
        return key in f.read().splitlines()

def mark_as_sent(m_id, cat=""):
    with open(DB_FILE, "a") as f:
        f.write(f"{m_id}_{cat}\n")

def save_to_history(m_dt, sport, match_name, pick, odd):
    try:
        line = f"{m_dt}|{sport}|{match_name}|{pick}|{odd}\n"
        with open(HISTORY_FILE, "a", encoding="utf-8") as f:
            f.write(line)
    except:
        pass

def run_pro_radar():
    now = datetime.now(timezone.utc)
    
    # TEST POŁĄCZENIA - Jeśli chcesz widzieć czy bot żyje, odkomentuj linię poniżej
    # send_msg("🔄 Bot sprawdza ofertę...")

    for sport_key in ['soccer_epl', 'soccer_spain_la_liga', 'soccer_poland_ekstraklasa', 'basketball_nba']:
        res = None
        for key in API_KEYS:
            url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/?apiKey={key}&regions=eu&markets=h2h"
            r = requests.get(url)
            if r.status_code == 200:
                res = r.json()
                break
        
        if not res: continue

        for match in res:
            m_id = match['id']
            home, away = match['home_team'], match['away_team']
            m_dt = datetime.strptime(match['commence_time'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            
            # Filtr 3 dni
            if m_dt > now + timedelta(days=3): continue

            try:
                # Pobieranie kursów
                odds_list = []
                for bm in match['bookmakers']:
                    for mkt in bm['markets']:
                        if mkt['key'] == 'h2h':
                            h = next(o['price'] for o in mkt['outcomes'] if o['name'] == home)
                            a = next(o['price'] for o in mkt['outcomes'] if o['name'] == away)
                            odds_list.append((h, a))
                
                if not odds_list: continue
                
                avg_h = sum(o[0] for o in odds_list) / len(odds_list)
                avg_a = sum(o[1] for o in odds_list) / len(odds_list)

                # Przykładowy warunek: kurs na faworyta < 1.70
                if avg_h < 1.70 and not is_already_sent(m_id, "h"):
                    msg = f"🔥 *PEWNIAK* ({sport_key})\n🏟️ {home} - {away}\n✅ Typ: *{home}*\n📈 Kurs: `{avg_h:.2f}`"
                    if send_msg(msg):
                        mark_as_sent(m_id, "h")
                        save_to_history(m_dt.strftime("%Y-%m-%d"), sport_key, f"{home}-{away}", home, f"{avg_h:.2f}")

                elif avg_a < 1.70 and not is_already_sent(m_id, "a"):
                    msg = f"🔥 *PEWNIAK* ({sport_key})\n🏟️ {home} - {away}\n✅ Typ: *{away}*\n📈 Kurs: `{avg_a:.2f}`"
                    if send_msg(msg):
                        mark_as_sent(m_id, "a")
                        save_to_history(m_dt.strftime("%Y-%m-%d"), sport_key, f"{home}-{away}", away, f"{avg_a:.2f}")

            except:
                continue

if __name__ == "__main__":
    run_pro_radar()
