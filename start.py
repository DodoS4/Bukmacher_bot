import requests
import os
import time
from datetime import datetime, timedelta, timezone

# --- KONFIGURACJA ---
T_TOKEN = os.getenv('T_TOKEN')
T_CHAT = os.getenv('T_CHAT')
RAPID_KEY = os.getenv('RAPIDAPI_KEY')
API_KEYS = [os.getenv('ODDS_KEY'), os.getenv('ODDS_KEY_2'), os.getenv('ODDS_KEY_3')]
API_KEYS = [k for k in API_KEYS if k]

DB_FILE = "sent_matches.txt"
HISTORY_FILE = "history.txt"

def send_msg(txt):
    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
    payload = {'chat_id': T_CHAT, 'text': txt, 'parse_mode': 'Markdown', 'disable_web_page_preview': True}
    try: requests.post(url, json=payload, timeout=10)
    except: pass

def get_football_result(match_name, date_str):
    """Próbuje pobrać wynik meczu z API-Football."""
    if not RAPID_KEY: return None
    url = "https://api-football-v1.p.rapidapi.com/v3/fixtures"
    headers = {"X-RapidAPI-Key": RAPID_KEY, "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"}
    
    # Przykładowe wyszukiwanie po dacie (wymaga dopracowania mapowania nazw)
    # Na razie zwracamy status 'Do sprawdzenia', aby nie blokować bota
    return "PENDING"

def send_daily_report():
    if not os.path.exists(HISTORY_FILE): return
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    report = []
    
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    for line in lines:
        if line.startswith(yesterday):
            dt, sport, match, pick, odd = line.strip().split('|')
            # Tutaj w przyszłości bot sam dopisze ✅ lub ❌
            google_link = f"https://www.google.com/search?q={match.replace(' ', '+')}+wynik"
            report.append(f"🏟️ *{match}*\n🎯 Typ: {pick} ({odd})\n🔗 [SPRAWDŹ WYNIK]({google_link})")

    if report:
        msg = f"📊 *RAPORT Z WCZORAJSZYCH TYPÓW ({yesterday})*\n\n" + "\n\n".join(report)
        send_msg(msg)

def run_pro_radar():
    now = datetime.now(timezone.utc)
    if now.hour == 10: send_daily_report()

    for sport_key, sport_label in {
        'soccer_epl': '⚽ PREMIER LEAGUE',
        'soccer_spain_la_liga': '⚽ LA LIGA',
        'soccer_germany_bundesliga': '⚽ BUNDESLIGA',
        'soccer_italy_serie_a': '⚽ SERIE A',
        'soccer_poland_ekstraklasa': '⚽ EKSTRAKLASA',
        'basketball_nba': '🏀 NBA',
        'icehockey_nhl': '🏒 NHL'
    }.items():
        res = None
        for key in API_KEYS:
            url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/?apiKey={key}&regions=eu&markets=h2h"
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                res = r.json()
                break
        
        if not res: continue

        for match in res:
            m_id = match['id']
            home, away = match['home_team'], match['away_team']
            m_dt = datetime.strptime(match['commence_time'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            
            if m_dt > now + timedelta(days=3): continue

            try:
                # Logika wyliczania średniej i szukania value (taka jak wcześniej)
                # ... [kod obliczeń kursów] ...
                # Jeśli bot znajdzie typ, zapisuje do history.txt
                # save_to_history(m_dt.strftime("%Y-%m-%d"), sport_label, f"{home}-{away}", pick, odd)
                pass 
            except: continue

# [Pełna wersja kodu z poprzedniej wiadomości z dodanym RAPID_KEY w env]
