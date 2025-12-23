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
    'soccer_italy_serie_a': '⚽ SERIE A',
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
    # Klucz ID meczu + kategoria pozwala wysłać ten sam mecz ponownie, 
    # jeśli np. nagle stał się "Value Betem" lub "Dropping Odds"
    unique_key = f"{match_id}_{category}"
    if not os.path.exists(DB_FILE): return False
    with open(DB_FILE, "r") as f:
        return unique_key in f.read().splitlines()

def mark_as_sent(match_id, category=""):
    with open(DB_FILE, "a") as f:
        f.write(f"{match_id}_{category}\n")

def run_pro_radar():
    if not ODDS_KEY: return
    now = datetime.now(timezone.utc)
    
    for sport_key, sport_label in SPORTS_CONFIG.items():
        try:
            # Pobieramy dane od wielu bukmacherów (regions=eu)
            url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/?apiKey={ODDS_KEY}&regions=eu&markets=h2h"
            res = requests.get(url, timeout=10).json()

            for match in res:
                m_id = match['id']
                home = match['home_team']
                away = match['away_team']
                
                # ZBIERANIE KURSÓW OD WSZYSTKICH BUKMACHERÓW
                all_home_odds = []
                all_away_odds = []
                
                for bm in match['bookmakers']:
                    for market in bm['markets']:
                        if market['key'] == 'h2h':
                            h_odd = next(o['price'] for o in market['outcomes'] if o['name'] == home)
                            a_odd = next(o['price'] for o in market['outcomes'] if o['name'] == away)
                            all_home_odds.append(h_odd)
                            all_away_odds.append(a_odd)

                if not all_home_odds: continue

                avg_h = sum(all_home_odds) / len(all_home_odds)
                max_h = max(all_home_odds)
                m_dt = datetime.strptime(match['commence_time'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)

                # --- STRATEGIA 1: VALUE BET (Błąd bukmachera) ---
                # Jeśli najlepszy kurs jest o 12% wyższy niż średnia rynkowa
                if max_h > (avg_h * 1.12) and not is_already_sent(m_id, "value"):
                    msg = (f"💎 *PRO-VALUE BET* 💎\n"
                           f"🏆 {sport_label}\n"
                           f"⚔️ *{home}* vs *{away}*\n"
                           f"📈 Rynek oferuje: `{max_h}` (Średnia: {avg_h:.2f})\n"
                           f"📢 *Bukmacher zaspał! Warto grać na {home}.*")
                    send_msg(msg)
                    mark_as_sent(m_id, "value")

                # --- STRATEGIA 2: PEWNIAKI + PODPÓRKI ---
                min_avg = min(avg_h, (sum(all_away_odds)/len(all_away_odds)))
                if min_avg <= 1.75 and not is_already_sent(m_id, "daily"):
                    tag = "🔥 *PEWNIAK* 🔥" if min_avg <= 1.35 else "⭐ *WARTE UWAGI* ⭐"
                    
                    # Sugestia Podpórki (Double Chance) dla piłki
                    sugestia = ""
                    if "⚽" in sport_label and min_avg > 1.40:
                        sugestia = "\n🛡️ *Bezpieczniej:* Zagraj z podpórką (1X/X2)"

                    msg = (f"{tag}\n"
                           f"🏆 {sport_label}\n"
                           f"⚔️ *{home}* vs *{away}*\n"
                           f"📊 Średni kurs: `{min_avg:.2f}`\n"
                           f"⏰ Start: `{m_dt.strftime('%d.%m %H:%M')}`{sugestia}")
                    
                    send_msg(msg)
                    mark_as_sent(m_id, "daily")

            time.sleep(1)
        except Exception as e:
            print(f"Błąd {sport_key}: {e}")

if __name__ == "__main__":
    run_pro_radar()
