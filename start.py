import requests, json, os
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from dateutil import parser

# ================= CONFIG (TAKTYKA STABILNA) =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")
TAX_PL = 0.88 
MIN_EDGE = 0.02   # Szukamy min. 2% przewagi (bezpieczniejszy zysk)
MIN_ODDS = 1.35   # Unikamy bardzo niskich kursów
MAX_ODDS = 3.20   # Odcinamy wysokie ryzyko (max kurs 3.20)
STAWKA = 100      
SCAN_DAYS = 120   # Skanowanie 5 dni do przodu

API_KEYS = [os.getenv(f"ODDS_KEY{i}") for i in ["", "_2", "_3", "_4", "_5"]]
API_KEYS = [k for k in API_KEYS if k]

# LIGI O NAJWIĘKSZEJ STABILNOŚCI (W TYM NHL)
LEAGUES = {
    "basketball_nba": "🏀 NBA",
    "basketball_euroleague": "🏀 Euroleague",
    "icehockey_nhl": "🏒 NHL",
    "tennis_atp_australian_open": "🎾 ATP AusOpen",
    "tennis_wta_australian_open": "🎾 WTA AusOpen",
    "soccer_poland_ekstraklasa": "⚽ Ekstraklasa",
    "soccer_england_premier_league": "⚽ Premier League",
    "soccer_spain_la_liga": "⚽ La Liga",
    "soccer_germany_bundesliga": "⚽ Bundesliga",
    "soccer_italy_serie_a": "⚽ Serie A",
    "esports_csgo_esl_pro_league": "🎮 CS:GO ESL"
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
    print(f"🔍 START SKANU (STABILNY): {datetime.now().strftime('%H:%M:%S')}")
    coupons = load_json(COUPONS_FILE, [])
    now = datetime.now(timezone.utc)
    existing_ids = {f"{c.get('home')}_{c.get('pick')}" for c in coupons}
    
    # Statystyki skanu do logów
    debug_stats = {"total": 0, "sent": 0, "out_of_range": 0, "low_edge": 0, "dup": 0}

    for l_key, l_name in LEAGUES.items():
        print(f"📡 Sprawdzam: {l_name}...")
        events = fetch_odds(l_key)
        if not events:
            print(f"   ℹ️ Brak ofert.")
            continue
        
        for e in events:
            home, away = e['home_team'], e['away_team']
            dt = parser.isoparse(e["commence_time"])
            
            # Filtr czasu
            if not (now <= dt <= now + timedelta(hours=SCAN_DAYS)): continue
            
            odds_map = defaultdict(list)
            for bm in e["bookmakers"]:
                for m in bm["markets"]:
                    for o in m["outcomes"]: odds_map[o["name"]].append(o["price"])
            
            # Wymagamy minimum 2 bukmacherów do porównania
            best_odds = {n: max(l) for n, l in odds_map.items() if len(l) >= 2}
            if len(best_odds) != 2: continue 
            
            inv = {k: 1/v for k, v in best_odds.items()}
            s = sum(inv.values())
            probs = {k: v/s for k, v in inv.items()}

            for sel, prob in probs.items():
                o = best_odds[sel]
                debug_stats["total"] += 1

                # 1. FILTR KURSÓW (Taktyka stabilna)
                if not (MIN_ODDS <= o <= MAX_ODDS):
                    debug_stats["out_of_range"] += 1
                    continue

                # 2. OBLICZENIE PRZEWAGI (Z uwzględnieniem podatku)
                edge = (prob - 1/(o * TAX_PL))
                
                # 3. SPRAWDZENIE DUPLIKATÓW
                if f"{home}_{sel}" in existing_ids:
                    debug_stats["dup"] += 1
                    continue

                # 4. DECYZJA O WYŁANIU ALERTU
                if edge >= MIN_EDGE:
                    local_dt = dt.astimezone(timezone(timedelta(hours=1)))
                    date_str = local_dt.strftime("%d.%m o %H:%M")

                    msg = (f"✅ <b>STABILNA OKAZJA ({l_name})</b>\n━━━━━━━━━━━━━━━━━━━━\n"
                           f"🏟 <b>{home} vs {away}</b>\n"
                           f"⏰ Start: <b>{date_str}</b>\n\n"
                           f"🔸 Typ: <b>{sel}</b>\n🔹 Kurs: <b>{o}</b>\n"
                           f"📈 Edge: <b>+{edge*100:.1f}%</b>\n💰 Stawka: <b>{STAWKA} zł</b>\n"
                           f"━━━━━━━━━━━━━━━━━━━━")
                    send_msg(msg)
                    
                    coupons.append({
                        "home": home, "away": away, "pick": sel, "odds": o, 
                        "stake": float(STAWKA), "status": "PENDING", 
                        "league_key": l_key, "league_name": l_name, 
                        "date": dt.isoformat(), "edge": round(edge*100, 2)
                    })
                    existing_ids.add(f"{home}_{sel}")
                    debug_stats["sent"] += 1
                else:
                    debug_stats["low_edge"] += 1
    
    save_json(COUPONS_FILE, coupons)
    
    print("\n" + "="*50)
    print("📊 PODSUMOWANIE SKANU (TAKTYKA STABILNA)")
    print(f"✅ Wysłano: {debug_stats['sent']}")
    print(f"♻️ Pominięto duplikatów: {debug_stats['dup']}")
    print(f"📉 Odrzucono (Zbyt niski Edge): {debug_stats['low_edge']}")
    print(f"🚫 Odrzucono (Kurs poza zakresem): {debug_stats['out_of_range']}")
    print("="*50 + "\n")

if __name__ == "__main__":
    run_scanner()
