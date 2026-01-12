import requests, json, os
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from dateutil import parser

# ================= CONFIG (TAKTYKA: MAKSYMALNA AKTYWNOŚĆ) =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")
TAX_PL = 0.88 
MIN_EDGE = 0.005  # Próg 0.5% - Maksymalna liczba okazji
MIN_ODDS = 1.35   
MAX_ODDS = 3.20   
STAWKA = 100      
SCAN_DAYS = 5     # Szukamy meczów na najbliższe 5 dni

# Obsługa 5 kluczy API
API_KEYS = [os.getenv(f"ODDS_KEY{i}") for i in ["", "_2", "_3", "_4", "_5"]]
API_KEYS = [k for k in API_KEYS if k]

# ELITARNA LISTA 10 LIG
LEAGUES = {
    "basketball_nba": "🏀 NBA",
    "icehockey_nhl": "🏒 NHL",
    "basketball_euroleague": "🏀 Euroleague",
    "soccer_poland_ekstraklasa": "⚽ Ekstraklasa",
    "soccer_england_premier_league": "⚽ Premier League",
    "soccer_spain_la_liga": "⚽ La Liga",
    "soccer_germany_bundesliga": "⚽ Bundesliga",
    "soccer_italy_serie_a": "⚽ Serie A",
    "tennis_atp_australian_open": "🎾 ATP AusOpen",
    "tennis_wta_australian_open": "🎾 WTA AusOpen"
}

COUPONS_FILE = "coupons.json"

# ================= FUNKCJE POMOCNICZE =================

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

def fetch_odds(league_key):
    # Próbuje użyć kluczy po kolei, jeśli jeden padnie (limit), bierze następny
    for key in API_KEYS:
        url = f"https://api.the-odds-api.com/v4/sports/{league_key}/odds"
        params = {"apiKey": key, "markets": "h2h", "regions": "eu"}
        r = requests.get(url, params=params)
        if r.status_code == 200: 
            return r.json()
        elif r.status_code == 429:
            print(f"⚠️ Klucz API limitowany, sprawdzam kolejny...")
            continue
    return None

# ================= GŁÓWNY SKANER =================

def run_scanner():
    print(f"🚀 START SKANU (EDGE 0.5%): {datetime.now().strftime('%H:%M:%S')}")
    coupons = load_json(COUPONS_FILE, [])
    now = datetime.now(timezone.utc)
    
    # Tworzymy zestaw ID, żeby nie wysyłać dwa razy tego samego
    existing_ids = {f"{c.get('home')}_{c.get('pick')}" for c in coupons}
    
    debug_stats = {"total": 0, "sent": 0, "out_of_range": 0, "low_edge": 0, "dup": 0}

    for l_key, l_name in LEAGUES.items():
        print(f"📡 Skanuję: {l_name}...")
        events = fetch_odds(l_key)
        if not events: continue
        
        for e in events:
            home, away = e['home_team'], e['away_team']
            dt = parser.isoparse(e["commence_time"])
            
            # Filtrujemy mecze tylko w przyszłości (do 5 dni)
            if not (now <= dt <= now + timedelta(days=SCAN_DAYS)): continue
            
            # Zbieramy kursy od wszystkich bukmacherów
            odds_map = defaultdict(list)
            for bm in e["bookmakers"]:
                for m in bm["markets"]:
                    if m["key"] == "h2h":
                        for o in m["outcomes"]: 
                            odds_map[o["name"]].append(o["price"])
            
            # Szukamy najlepszego kursu na każdy wynik
            best_odds = {n: max(l) for n, l in odds_map.items() if len(l) >= 2}
            if len(best_odds) < 2: continue 
            
            # Obliczanie prawdopodobieństwa (Fair Odds)
            inv = {k: 1/v for k, v in best_odds.items()}
            s = sum(inv.values())
            probs = {k: (1/v)/s for k, v in best_odds.items()}

            for sel, prob in probs.items():
                o = best_odds[sel]
                debug_stats["total"] += 1

                # 1. Filtr kursu
                if not (MIN_ODDS <= o <= MAX_ODDS):
                    debug_stats["out_of_range"] += 1
                    continue

                # 2. Obliczanie Edge (uwzględniając podatek)
                edge = (prob - 1/(o * TAX_PL))
                
                # 3. Sprawdzenie czy już mamy ten typ
                if f"{home}_{sel}" in existing_ids:
                    debug_stats["dup"] += 1
                    continue

                # 4. Decyzja o wysłaniu
                if edge >= MIN_EDGE:
                    # Konwersja czasu na polski (UTC+1)
                    local_dt = dt.astimezone(timezone(timedelta(hours=1)))
                    date_str = local_dt.strftime("%d.%m o %H:%M")

                    msg = (f"🔥 <b>OKAZJA 0.5% ({l_name})</b>\n"
                           f"━━━━━━━━━━━━━━━━━━━━\n"
                           f"🏟 <b>{home} vs {away}</b>\n"
                           f"⏰ Start: <b>{date_str}</b>\n\n"
                           f"🔸 Typ: <b>{sel}</b>\n"
                           f"🔹 Kurs: <b>{o}</b>\n"
                           f"📈 Edge: <b>+{edge*100:.2f}%</b>\n"
                           f"💰 Stawka: <b>{STAWKA} zł</b>\n"
                           f"━━━━━━━━━━━━━━━━━━━━")
                    
                    send_msg(msg)
                    
                    # Zapis do bazy kuponów
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
    print(f"\n✅ KONIEC: Wysłano: {debug_stats['sent']} | Za niski Edge: {debug_stats['low_edge']} | Duplikaty: {debug_stats['dup']}")

if __name__ == "__main__":
    run_scanner()
