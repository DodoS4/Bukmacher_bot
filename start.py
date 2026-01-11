import requests, json, os
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from dateutil import parser

# ================= CONFIG =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")
TAX_PL = 0.88 
MIN_EDGE = 0.005  # Obniżone do 0.5% - więcej okazji przy 12% podatku
STAWKA = 100      # Kwota w zł
SCAN_DAYS = 120   # Skanowanie 5 dni do przodu

API_KEYS = [os.getenv(f"ODDS_KEY{i}") for i in ["", "_2", "_3", "_4", "_5"]]
API_KEYS = [k for k in API_KEYS if k]

# MAKSYMALNA LISTA LIG (Różne strefy czasowe i sporty)
LEAGUES = {
    # --- ESPORT ---
    "esports_csgo_blast_premier": "🎮 CS:GO BLAST",
    "esports_csgo_esl_pro_league": "🎮 CS:GO ESL Pro",
    "esports_league_of_legends_lck": "🎮 LoL LCK",
    "esports_league_of_legends_lpl": "🎮 LoL LPL",
    # --- TENIS ---
    "tennis_atp_challenger_tour": "🎾 ATP Challengers",
    "tennis_wta_1000": "🎾 WTA 1000",
    # --- KOSZYKÓWKA ---
    "basketball_nba": "🏀 NBA",
    "basketball_euroleague": "🏀 Euroleague",
    "basketball_korea_kbl": "🏀 Korea KBL",
    "basketball_spain_liga_acb": "🏀 Hiszpania ACB",
    # --- PIŁKA NOŻNA (2-way / DNB) ---
    "soccer_poland_ekstraklasa": "⚽ Ekstraklasa",
    "soccer_england_championship": "⚽ Anglia Champ.",
    "soccer_england_league1": "⚽ Anglia L1",
    "soccer_italy_serie_b": "⚽ Włochy B",
    "soccer_germany_bundesliga2": "⚽ Niemcy 2",
    # --- HOKEJ ---
    "icehockey_nhl": "🏒 NHL",
    "icehockey_sweden_allsvenskan": "🏒 Szwecja Allsv.",
    # --- SIATKÓWKA ---
    "volleyball_poland_plusliga": "🏐 PlusLiga (PL)",
    "volleyball_italy_superlega": "🏐 Siatkówka Włochy"
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
    print(f"🔍 START SKANU: {datetime.now().strftime('%H:%M:%S')}")
    coupons = load_json(COUPONS_FILE, [])
    now = datetime.now(timezone.utc)
    existing_ids = {f"{c.get('home')}_{c.get('pick')}" for c in coupons}
    
    debug_low_edge = []
    debug_no_comp = []
    counts = {"sent": 0, "dup": 0, "checked_leagues": 0}

    for l_key, l_name in LEAGUES.items():
        print(f"📡 Sprawdzam: {l_name}...")
        counts["checked_leagues"] += 1
        events = fetch_odds(l_key)
        
        if not events:
            print(f"   ℹ️ Brak ofert.")
            continue
        
        for e in events:
            home, away = e['home_team'], e['away_team']
            dt = parser.isoparse(e["commence_time"])
            
            if not (now <= dt <= now + timedelta(hours=SCAN_DAYS)): continue
            
            odds_map = defaultdict(list)
            for bm in e["bookmakers"]:
                for m in bm["markets"]:
                    for o in m["outcomes"]: odds_map[o["name"]].append(o["price"])
            
            best_odds = {n: max(l) for n, l in odds_map.items() if len(l) >= 2}
            
            if len(best_odds) != 2:
                debug_no_comp.append(f"{l_name}: {home}-{away}")
                continue 
            
            inv = {k: 1/v for k, v in best_odds.items()}
            s = sum(inv.values())
            probs = {k: v/s for k, v in inv.items()}

            for sel, prob in probs.items():
                o = best_odds[sel]
                edge = (prob - 1/(o * TAX_PL))
                
                if f"{home}_{sel}" in existing_ids:
                    counts["dup"] += 1
                    continue

                if edge >= MIN_EDGE:
                    local_dt = dt.astimezone(timezone(timedelta(hours=1)))
                    date_str = local_dt.strftime("%d.%m o %H:%M")

                    msg = (f"🎯 <b>OKAZJA ({l_name})</b>\n━━━━━━━━━━━━━━━━━━━━\n"
                           f"🏟 <b>{home} vs {away}</b>\n"
                           f"⏰ Start: <b>{date_str}</b>\n\n"
                           f"🔸 Typ: <b>{sel}</b>\n🔹 Kurs: <b>{o}</b> (netto: {round(o*0.88, 2)})\n"
                           f"📈 Edge: <b>+{edge*100:.1f}%</b>\n💰 Stawka: <b>{STAWKA} zł</b>\n"
                           f"━━━━━━━━━━━━━━━━━━━━")
                    send_msg(msg)
                    coupons.append({"home": home, "away": away, "pick": sel, "odds": o, "stake": float(STAWKA), "status": "PENDING", "league_key": l_key, "league_name": l_name, "date": dt.isoformat(), "edge": round(edge*100, 2)})
                    existing_ids.add(f"{home}_{sel}")
                    counts["sent"] += 1
                else:
                    if edge > -0.05:
                        debug_low_edge.append(f"{l_name}: {home}-{away} ({sel}) | Edge: {round(edge*100, 2)}%")
    
    save_json(COUPONS_FILE, coupons)
    
    print("\n" + "="*50)
    print("📊 PODSUMOWANIE SKANU")
    print(f"✅ Wysłano: {counts['sent']} | ♻️ Duplikaty: {counts['dup']}")
    print(f"❌ Odrzucono (Edge): {len(debug_low_edge)} | ⚠️ Brak por.: {len(debug_no_comp)}")
    print("="*50 + "\n")

if __name__ == "__main__":
    run_scanner()
