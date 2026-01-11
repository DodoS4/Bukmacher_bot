import requests, json, os
from datetime import datetime, timezone

# ================= CONFIG =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS")
TAX_PL = 1.0  # Bez podatku zgodnie z Twoim życzeniem

# Pobieramy wszystkie 5 kluczy API z sekretów GitHub
API_KEYS = [
    os.getenv("ODDS_KEY"), 
    os.getenv("ODDS_KEY_2"), 
    os.getenv("ODDS_KEY_3"), 
    os.getenv("ODDS_KEY_4"), 
    os.getenv("ODDS_KEY_5")
]
API_KEYS = [k for k in API_KEYS if k] # Filtrujemy tylko te, które istnieją

BANKROLL_FILE = "bankroll.json"
COUPONS_FILE = "coupons.json"

def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f: return json.load(f)
        except: pass
    return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f: json.dump(data, f, indent=2)

def send_result_msg(txt):
    # Wysyłka na T_CHAT_RESULTS (drugie konto)
    target = T_CHAT_RESULTS if T_CHAT_RESULTS else os.getenv("T_CHAT")
    if not T_TOKEN or not target: return
    try:
        requests.post(f"https://api.telegram.org/bot{T_TOKEN}/sendMessage", 
                     json={"chat_id": target, "text": txt, "parse_mode": "HTML"})
    except: pass

def get_scores(league_key):
    """Próbuje pobrać wyniki używając dostępnych kluczy API."""
    for key in API_KEYS:
        url = f"https://api.the-odds-api.com/v4/sports/{league_key}/scores"
        r = requests.get(url, params={"apiKey": key, "daysFrom": 3})
        if r.status_code == 200:
            return r.json()
        elif r.status_code == 429:
            continue # Klucz wyczerpany, próbuj następny
    return None

def run_settler():
    print("--- ROZLICZANIE WYNIKÓW ---")
    bank_data = load_json(BANKROLL_FILE, {"bankroll": 1000.0})
    coupons = load_json(COUPONS_FILE, [])
    
    pending_leagues = {c['league_key'] for c in coupons if c['status'] == 'PENDING'}
    
    results_cache = {}
    for l_key in pending_leagues:
        scores = get_scores(l_key)
        if scores:
            results_cache[l_key] = scores

    for c in coupons:
        if c['status'] != 'PENDING': continue
        
        match = next((m for m in results_cache.get(c['league_key'], []) 
                    if m['home_team'] == c['home'] and m['completed']), None)
        
        if match:
            try:
                # Wyciąganie wyników
                s_dict = {s['name']: int(s['score']) for s in match['scores']}
                h_score = s_dict[c['home']]
                a_score = s_dict[c['away']]
                
                winner = c['home'] if h_score > a_score else (c['away'] if a_score > h_score else "Draw")
                
                if c['pick'] == winner:
                    win_amount = round(c['stake'] * c['odds'] * TAX_PL, 2)
                    bank_data["bankroll"] += win_amount
                    c['status'] = 'WON'
                    msg = (f"✅ <b>WYGRANA!</b>\n"
                           f"━━━━━━━━━━━━━━━━━━━━\n"
                           f"🏟 {c['home']} - {c['away']}\n"
                           f"🎯 Wynik: {h_score}:{a_score}\n"
                           f"💰 Zysk: <b>+{win_amount:.2f} PLN</b>\n"
                           f"🏦 Bankroll: {bank_data['bankroll']:.2f} PLN")
                else:
                    c['status'] = 'LOST'
                    msg = (f"❌ <b>PRZEGRANA</b>\n"
                           f"━━━━━━━━━━━━━━━━━━━━\n"
                           f"🏟 {c['home']} - {c['away']}\n"
                           f"🎯 Wynik: {h_score}:{a_score}\n"
                           f"📉 Strata: -{c['stake']:.2f} PLN")
                
                send_result_msg(msg)
            except Exception as e:
                print(f"Błąd rozliczania meczu: {e}")

    save_json(COUPONS_FILE, coupons)
    save_json(BANKROLL_FILE, bank_data)

if __name__ == "__main__":
    run_settler()
