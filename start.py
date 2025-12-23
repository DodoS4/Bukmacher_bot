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
    except: pass

def is_already_sent(match_id, category=""):
    unique_key = f"{match_id}_{category}"
    if not os.path.exists(DB_FILE): return False
    with open(DB_FILE, "r") as f:
        return unique_key in f.read().splitlines()

def mark_as_sent(match_id, category=""):
    with open(DB_FILE, "a") as f:
        f.write(f"{match_id}_{category}\n")

def run_radar():
    if not ODDS_KEY: return
    now = datetime.now(timezone.utc)
    
    # RAPORT PORANNY STATUSU
    if now.hour == 0 or os.getenv('GITHUB_EVENT_NAME') == 'workflow_dispatch':
        send_msg(f"🟢 *SYSTEM AKTYWNY*\n📅 `{now.strftime('%d.%m.%Y')}`\n✅ Skanowanie ofert w toku...")

    for sport_key, sport_label in SPORTS_CONFIG.items():
        try:
            url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/?apiKey={ODDS_KEY}&regions=eu&markets=h2h"
            response = requests.get(url, timeout=10)
            if response.status_code != 200: continue
            data = response.json()

            for match in data:
                m_id = match['id']
                home = match['home_team']
                away = match['away_team']
                m_dt = datetime.strptime(match['commence_time'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)

                # Analiza kursów u wszystkich dostępnych bukmacherów
                all_h, all_a = [], []
                for bm in match['bookmakers']:
                    for mkt in bm['markets']:
                        if mkt['key'] == 'h2h':
                            try:
                                h_o = next(o['price'] for o in mkt['outcomes'] if o['name'] == home)
                                a_o = next(o['price'] for o in mkt['outcomes'] if o['name'] == away)
                                all_h.append(h_o)
                                all_a.append(a_o)
                            except: continue

                if not all_h: continue

                avg_h, max_h = sum(all_h)/len(all_h), max(all_h)
                avg_a, max_a = sum(all_a)/len(all_a), max(all_a)

                # 1. WYKRYWANIE BŁĘDU BUKMACHERA (VALUE BET)
                if (max_h > avg_h * 1.12 or max_a > avg_a * 1.12) and not is_already_sent(m_id, "value"):
                    winner = home if max_h > avg_h * 1.12 else away
                    best_o = max_h if max_h > avg_h * 1.12 else max_a
                    avg_o = avg_h if max_h > avg_h * 1.12 else avg_a
                    
                    msg = (f"💎 *BUKMACHER ZASPAŁ!* 💎\n🏆 {sport_label}\n"
                           f"━━━━━━━━━━━━━━━\n"
                           f"✅ STAWIAJ NA: *{winner.upper()}*\n\n"
                           f"📈 Kurs OKAZJA: `{best_o:.2f}`\n"
                           f"📊 Średnia rynkowa: `{avg_o:.2f}`\n"
                           f"━━━━━━━━━━━━━━━\n"
                           f"📢 _Zawyżony kurs znaleziony!_")
                    send_msg(msg)
                    mark_as_sent(m_id, "value")

                # 2. WYKRYWANIE PEWNIAKÓW I WARTYCH UWAGI
                min_avg = min(avg_h, avg_a)
                if min_avg <= 1.75 and not is_already_sent(m_id, "daily"):
                    tag = "🔥 *PEWNIAK*" if min_avg <= 1.35 else "⭐ *WARTE UWAGI*"
                    
                    if avg_h < avg_a:
                        pick_txt = f"✅ STAWIAJ NA: *{home.upper()}*\n\n🟢 *{home}*: `{avg_h:.2f}`\n⚪ {away}: `{avg_a:.2f}`"
                    else:
                        pick_txt = f"✅ STAWIAJ NA: *{away.upper()}*\n\n⚪ {home}: `{avg_h:.2f}`\n🟢 *{away}*: `{avg_a:.2f}`"

                    sugestia = "\n🛡️ _Sugerowana podpórka (1X/X2)_" if "⚽" in sport_label and min_avg > 1.40 else ""
                    
                    msg = (f"{tag}\n🏆 {sport_label}\n"
                           f"━━━━━━━━━━━━━━━\n"
                           f"{pick_txt}\n"
                           f"━━━━━━━━━━━━━━━\n"
                           f"⏰ `{m_dt.strftime('%d.%m %H:%M')}` UTC{sugestia}")
                    
                    send_msg(msg)
                    mark_as_sent(m_id, "daily")
            
            time.sleep(1)
        except: continue

if __name__ == "__main__":
    run_radar()
