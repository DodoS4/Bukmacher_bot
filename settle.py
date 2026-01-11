import requests, json, os
from datetime import datetime, timezone

T_TOKEN = os.getenv("T_TOKEN")
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS")
API_KEY = os.getenv("ODDS_KEY") # Jeden klucz wystarczy do wyników
COUPONS_FILE = "coupons.json"

def send_msg(txt):
    if not T_TOKEN or not T_CHAT_RESULTS: return
    requests.post(f"https://api.telegram.org/bot{T_TOKEN}/sendMessage", 
                 json={"chat_id": T_CHAT_RESULTS, "text": txt, "parse_mode": "HTML"})

def run_settler():
    if not os.path.exists(COUPONS_FILE): return
    with open(COUPONS_FILE, "r", encoding="utf-8") as f:
        coupons = json.load(f)

    pending = [c for c in coupons if c.get('status') == 'PENDING']
    if not pending: return

    # Grupowanie lig, żeby nie marnować zapytań API
    leagues = {c['league_key'] for c in pending}
    
    for l_key in leagues:
        url = f"https://api.the-odds-api.com/v4/sports/{l_key}/scores/"
        r = requests.get(url, params={"apiKey": API_KEY, "daysFrom": 3})
        
        if r.status_code != 200: continue
        scores = r.json()

        for c in coupons:
            if c.get('status') != 'PENDING' or c['league_key'] != l_key: continue
            
            # Szukanie meczu w wynikach
            match_score = next((s for s in scores if s['home_team'] == c['home'] or s['away_team'] == c['home']), None)
            
            if match_score and match_score.get('completed'):
                # Pobieranie punktów z obsługą błędów nazw (KeyError)
                try:
                    s_dict = {s['name']: int(s['score']) for s in match_score['scores']}
                    h_score = s_dict.get(c['home'])
                    a_score = s_dict.get(c['away'])
                    
                    if h_score is None or a_score is None: continue # Skip jeśli nazwa się nie zgadza

                    winner = c['home'] if h_score > a_score else c['away']
                    c['status'] = 'WON' if c['pick'] == winner else 'LOST'
                    
                    emoji = "✅" if c['status'] == 'WON' else "❌"
                    txt = (f"{emoji} <b>ROZLICZONO: {c['home']} - {c['away']}</b>\n"
                           f"Wynik: {h_score}:{a_score}\n"
                           f"Typ: {c['pick']} | Status: {c['status']}")
                    send_msg(txt)
                except:
                    continue

    with open(COUPONS_FILE, "w", encoding="utf-8") as f:
        json.dump(coupons, f, indent=2)

if __name__ == "__main__":
    run_settler()
