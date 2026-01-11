import requests, json, os
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from dateutil import parser

# ================= CONFIG =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")
# Podatek ustawiony na 1.0 (czysty zysk bez podatku w PL)
TAX_PL = 1.0  

# Parametry strategii
MIN_EDGE = 0.02    # Szukamy min. 2% przewagi
DAILY_LIMIT = 10   # Maksymalnie 10 nowych zakładów dziennie

API_KEYS = [k for k in [os.getenv("ODDS_KEY"), os.getenv("ODDS_KEY_2"), os.getenv("ODDS_KEY_3")] if k]
LEAGUES = {
    "soccer_epl": "⚽ EPL", 
    "soccer_spain_la_liga": "⚽ La Liga",
    "soccer_germany_bundesliga": "⚽ Bundesliga",
    "soccer_italy_serie_a": "⚽ Serie A",
    "basketball_nba": "🏀 NBA", 
    "icehockey_nhl": "🏒 NHL"
}

BANKROLL_FILE = "bankroll.json"
COUPONS_FILE = "coupons.json"

# ================= NARZĘDZIA =================
def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f: return json.load(f)
        except: pass
    return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f: json.dump(data, f, indent=2)

def send_msg(txt):
    if not T_TOKEN or not T_CHAT: return
    try:
        requests.post(f"https://api.telegram.org/bot{T_TOKEN}/sendMessage", 
                     json={"chat_id": T_CHAT, "text": txt, "parse_mode": "HTML"})
    except: pass

def no_vig_probs(odds):
    inv = {k: 1/v for k, v in odds.items() if v}
    s = sum(inv.values())
    return {k: v/s for k, v in inv.items()}

def get_kelly_stake(bankroll, prob, odds):
    if odds <= 1: return 0
    # Bezpieczne 1/8 Kelly dla kapitału 1000 zł
    kelly_pct = (prob * odds - 1) / (odds - 1)
    stake = bankroll * (max(0, kelly_pct) * 0.125) 
    # Max 5% bankrollu (50 zł) i min 2 zł
    return round(max(2.0, min(stake, bankroll * 0.05)), 2)

# ================= SCANNER =================
def run_scanner():
    print(f"🚀 Start skanowania: {datetime.now()}")
    bank_data = load_json(BANKROLL_FILE, {"bankroll": 1000.0})
    coupons = load_json(COUPONS_FILE, [])
    now = datetime.now(timezone.utc)
    
    potential_bets = []
    existing_ids = {f"{c.get('home')}_{c.get('pick')}" for c in coupons}
    
    for l_key, l_name in LEAGUES.items():
        for key in API_KEYS:
            try:
                r = requests.get(f"https://api.the-odds-api.com/v4/sports/{l_key}/odds",
                               params={"apiKey": key, "markets": "h2h", "regions": "eu"})
                if r.status_code != 200: continue
                events = r.json()
                
                for e in events:
                    dt = parser.isoparse(e["commence_time"])
                    if not (now <= dt <= now + timedelta(hours=48)): continue
                    
                    odds_map = defaultdict(list)
                    for bm in e["bookmakers"]:
                        for m in bm["markets"]:
                            for o in m["outcomes"]: 
                                odds_map[o["name"]].append(o["price"])
                    
                    best_odds = {n: max(l) for n, l in odds_map.items() if len(l) >= 2}
                    if len(best_odds) < 2: continue
                    
                    probs = no_vig_probs(best_odds)
                    for sel, prob in probs.items():
                        o = best_odds[sel]
                        edge = (prob - 1/(o * TAX_PL))
                        
                        bet_id = f"{e['home_team']}_{sel}"
                        if edge >= MIN_EDGE and bet_id not in existing_ids:
                            potential_bets.append({
                                "home": e['home_team'], "away": e['away_team'], "pick": sel,
                                "odds": o, "edge": edge, "prob": prob, "league_key": l_key,
                                "league_name": l_name, "dt": dt.isoformat()
                            })
                break # Przejdź do następnej ligi po sukcesie z jednym kluczem
            except: continue

    # Wybór 10 najlepszych i wysyłka Telegram
    potential_bets.sort(key=lambda x: x['edge'], reverse=True)
    
    added_count = 0
    for b in potential_bets[:DAILY_LIMIT]:
        stake = get_kelly_stake(bank_data["bankroll"], b['prob'], b['odds'])
        
        # Formatowanie wiadomości wg Twojego wzoru
        msg = (
            f"🎯 <b>NOWY TYP ({b['league_name']})</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🏟 <b>{b['home']} - {b['away']}</b>\n"
            f"📅 {parser.isoparse(b['dt']).strftime('%d.%m, %H:%M')}\n\n"
            f"🔸 Typ: <b>{b['pick']}</b>\n"
            f"🔹 Kurs: <b>{b['odds']}</b>\n\n"
            f"📊 ANALIZA MATEMATYCZNA:\n"
            f"📈 Przewaga (Edge): <b>+{b['edge']*100:.1f}%</b>\n"
            f"💰 Stawka (Kelly): <b>{stake:.2f} PLN</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Status: PENDING"
        )
        
        send_msg(msg)
        
        coupons.append({
            "home": b['home'], "away": b['away'], "pick": b['pick'], "odds": b['odds'],
            "stake": stake, "status": "PENDING", "league_key": b['league_key'],
            "league_name": b['league_name'], "date": b['dt'], "edge": round(b['edge']*100, 2)
        })
        bank_data["bankroll"] -= stake
        added_count += 1

    save_json(COUPONS_FILE, coupons)
    save_json(BANKROLL_FILE, {"bankroll": round(bank_data["bankroll"], 2)})
    print(f"Dodano kuponów: {added_count}")

if __name__ == "__main__":
    run_scanner()
