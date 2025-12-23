import requests
import os
import time
from datetime import datetime, timedelta, timezone

# --- KONFIGURACJA KLUCZY ---
T_TOKEN = os.getenv('T_TOKEN')
T_CHAT = os.getenv('T_CHAT')
GEMINI_KEY = os.getenv('GEMINI_KEY')
ODDS_KEY = os.getenv('ODDS_KEY')

# TWOJE DYSCYPLINY
SPORTS_CONFIG = {
    'soccer_epl': '⚽ PREMIER LEAGUE',
    'basketball_nba': '🏀 NBA',
    'icehockey_nhl': '🏒 NHL',
    'mma_mixed_martial_arts': '🥊 MMA/UFC',
    'americanfootball_nfl': '🏈 NFL'
}

DB_FILE = "sent_matches.txt"

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

def ask_gemini_expert(sport_label, home, away, odds_ctx):
    if not GEMINI_KEY: return "Brak analizy AI."
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"
    
    prompt = (f"Jesteś profesjonalnym typerem. Analizujesz {sport_label}: {home} vs {away}. "
              f"Kursy: {odds_ctx}. Podaj krótki typ, uzasadnienie i szansę w % (np. 75%). "
              "Max 50 słów. Pisz po polsku.")
    
    try:
        r = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=15)
        return r.json()['candidates'][0]['content']['parts'][0]['text']
    except:
        return "AI analizuje dane... Typ oparty na trendach rynkowych."

def run_multi_radar():
    if not ODDS_KEY:
        print("BŁĄD: Brak klucza ODDS_KEY!")
        return

    now = datetime.now(timezone.utc)
    # KLUCZOWA ZMIANA: Zasięg ustawiony na pełne 7 dni
    future_window = now + timedelta(days=7) 

    print(f"--- START RADARU (7 DNI): {now.strftime('%Y-%m-%d %H:%M')} ---")

    for sport_key, sport_label in SPORTS_CONFIG.items():
        try:
            print(f"Skanowanie: {sport_label}...")
            # Pobieranie danych z The Odds API
            url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/?apiKey={ODDS_KEY}&regions=eu&markets=h2h"
            response = requests.get(url, timeout=10)
            
            if response.status_code != 200:
                print(f"API Error {sport_key}: {response.status_code}")
                continue
                
            matches = response.json()

            for match in matches:
                m_id = match['id']
                m_dt = datetime.strptime(match['commence_time'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)

                # Sprawdzenie czy mecz jest w oknie 7 dni i czy nie został już wysłany
                if now < m_dt < future_window and not is_already_sent(m_id):
                    home = match['home_team']
                    away = match['away_team']
                    
                    # Pobieranie kursów 1 i 2
                    try:
                        outcomes = match['bookmakers'][0]['markets'][0]['outcomes']
                        o_h = next(o['price'] for o in outcomes if o['name'] == home)
                        o_a = next(o['price'] for o in outcomes if o['name'] == away)
                        odds_info = f"1: {o_h} | 2: {o_a}"
                    except:
                        odds_info = "Kursy niedostępne"

                    # Analiza AI
                    analiza = ask_gemini_expert(sport_label, home, away, odds_info)

                    # Treść wiadomości
                    msg = (f"📅 *TYP NA NAJBLIŻSZY TYDZIEŃ* | {sport_label}\n"
                           f"⚔️ *{home}* vs *{away}*\n"
                           f"📊 {odds_info}\n\n"
                           f"🧠 *AI Typer:* _{analiza.strip()}_\n"
                           f"⏰ Start: `{m_dt.strftime('%d.%m o %H:%M')}` UTC")

                    send_msg(msg)
                    mark_as_sent(m_id)
                    print(f"Wysłano: {home} vs {away}")
                    time.sleep(2) # Ochrona przed spamem Telegrama
            
            time.sleep(1) # Przerwa między dyscyplinami dla API
        except Exception as e:
            print(f"Błąd w {sport_key}: {e}")

if __name__ == "__main__":
    run_multi_radar()
