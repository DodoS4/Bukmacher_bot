import requests, json, os
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from dateutil import parser

# ================= CONFIG =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")
TAX_PL = 0.88 
MIN_EDGE = 0.015  # 1.5% przewagi po podatku
STAWKA = 100      # Kwota w zł na jeden zakład

API_KEYS = [os.getenv(f"ODDS_KEY{i}") for i in ["", "_2", "_3", "_4", "_5"]]
API_KEYS = [k for k in API_KEYS if k]

LEAGUES = {
    # ESPORT
    "esports_csgo_blast_premier": "🎮 CS:GO BLAST",
    "esports_csgo_esl_pro_league": "🎮 CS:GO ESL Pro",
    "esports_league_of_legends_lck": "🎮 LoL LCK",
    "esports_league_of_legends_lpl": "🎮 LoL LPL",
    "esports_league_of_legends_lec": "🎮 LoL LEC",
    "esports_valorant_champions_tour": "🎮 Valorant VCT",
    # TENIS
    "tennis_atp_australian_open": "🎾 ATP Australian Open",
    "tennis_wta_australian_open": "🎾 WTA Australian Open",
    "tennis_atp_french_open": "🎾 ATP Roland Garros",
    # KOSZYKÓWKA
    "basketball_nba": "🏀 NBA",
    "basketball_euroleague": "🏀 Euroleague"
}

COUPONS_FILE = "coupons.json"

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
    try: requests.post(f"https://api.telegram.org/bot{T_TOKEN}/sendMessage", json={"chat_id": T_CHAT, "text": txt, "parse_mode": "HTML"})
    except: pass

def fetch_odds(league_key):
    for key in API_KEYS:
        r = requests.get(f"https://api.the-odds-api.com/v4/sports/{league_key}/odds", params={"apiKey": key, "markets": "h2h", "regions": "eu"})
        if r.status_code == 200: return r.json()
    return None

def run_scanner():
    print(f"🔍 SKAN START: {datetime.now().strftime('%H:%M:%S')}")
    coupons = load_json(COUPONS_FILE, [])
    now = datetime.now(timezone.utc)
    existing_ids = {f"{c.get('home')}_{c.get('pick')}" for c in coupons}
    
    for l_key, l_name in LEAGUES.items():
        print(f"📡 Skan: {l_name}...")
        events = fetch_odds(l_key)
        if not events: continue
        
        for e in events:
            home, away, dt = e['home_team'], e['away_team'], parser.isoparse(e["commence_time"])
            if not (now <= dt <= now + timedelta(hours=96)): continue
            
            odds_map = defaultdict(list)
            for bm in e["bookmakers"]:
                for m in bm["markets"]:
                    for o in m["outcomes"]: odds_map[o["name"]].append(o["price"])
            
            best_odds = {n: max(l) for n, l in odds_map.items() if len(l) >= 2}
            if len(best_odds) != 2: continue 
            
            inv = {k: 1/v for k, v in best_odds.items()}; s = sum(inv.values())
            probs = {k: v/s for k, v in inv.items()}

            for sel, prob in probs.items():
                o = best_odds[sel]
                edge = (prob - 1/(o * TAX_PL))
                
                if edge >= MIN_EDGE and f"{home}_{sel}" not in existing_ids:
                    # Czas PL
                    local_dt = dt.astimezone(timezone(timedelta(hours=1)))
                    date_str = local_dt.strftime("%d.%m o %H:%M")

                    msg = (f"🎯 <b>PROPOZYCJA 2-WAY ({l_name})</b>\n━━━━━━━━━━━━━━━━━━━━\n"
                           f"🏟 <b>{home} vs {away}</b>\n"
                           f"⏰ Start: <b>{date_str}</b>\n\n"
                           f"🔸 Typ: <b>{sel}</b>\n🔹 Kurs: <b>{o}</b> (netto: {round(o*0.88, 2)})\n"
                           f"📈 Edge: <b>+{edge*100:.1f}%</b>\n💰 Stawka: <b>{STAWKA} zł</b>\n"
                           f"━━━━━━━━━━━━━━━━━━━━")
                    send_msg(msg)
                    coupons.append({"home": home, "away": away, "pick": sel, "odds": o, "stake": float(STAWKA), "status": "PENDING", "league_key": l_key, "league_name": l_name, "date": dt.isoformat(), "edge": round(edge*100, 2)})
    
    save_json(COUPONS_FILE, coupons)
    print("🏁 Skan zakończony.")

if __name__ == "__main__": run_scanner()
