import requests, json, os
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from dateutil import parser

# ================= CONFIG =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")
TAX_PL = 1.0   # NO TAX
MIN_EDGE = 0.005  # 0.5%
STAWKA = 100
SCAN_DAYS = 45

API_KEYS = [os.getenv(f"ODDS_KEY{i}") for i in ["", "_2", "_3", "_4", "_5"]]
API_KEYS = [k for k in API_KEYS if k]

COUPONS_FILE = "coupons_notax.json"

# ================= LIGI =================
LEAGUES = {
    "basketball_nba": "🏀 NBA",
    "basketball_euroleague": "🏀 Euroleague",
    "basketball_spain_liga_acb": "🏀 Hiszpania ACB",
    "basketball_korea_kbl": "🏀 Korea KBL",
    "tennis_atp_challenger_tour": "🎾 ATP Challengers",
    "tennis_wta_1000": "🎾 WTA 1000",
    "soccer_england_league1": "⚽ Anglia L1",
    "soccer_england_championship": "⚽ Anglia Champ.",
    "soccer_italy_serie_b": "⚽ Włochy B",
    "soccer_poland_ekstraklasa": "⚽ Ekstraklasa",
    "icehockey_nhl": "🏒 NHL",
    "icehockey_sweden_allsvenskan": "🏒 Szwecja Allsv.",
    "volleyball_poland_plusliga": "🏐 PlusLiga (PL)",
    "volleyball_italy_superlega": "🏐 Siatkówka Włochy",
    "esports_csgo_blast_premier": "🎮 CS:GO BLAST"
}

# ================= FUNKCJE =================
def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path,"r",encoding="utf-8") as f: return json.load(f)
        except: pass
    return default

def save_json(path, data):
    with open(path,"w",encoding="utf-8") as f: json.dump(data,f,indent=2)
    print(f"[DEBUG] Zapisano {len(data)} zakładów do {path}")

def send_msg(txt):
    if not T_TOKEN or not T_CHAT: return
    try:
        requests.post(f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
                      json={"chat_id":T_CHAT,"text":txt,"parse_mode":"HTML"})
    except: pass

def fetch_odds(league_key):
    for key in API_KEYS:
        r = requests.get(f"https://api.the-odds-api.com/v4/sports/{league_key}/odds",
                         params={"apiKey":key,"markets":"h2h","regions":"eu"})
        if r.status_code == 200: return r.json()
    return None

# ================= SCANNER =================
def run_scanner():
    print(f"🔍 START SKANU: {datetime.now().strftime('%H:%M:%S')}")
    coupons = load_json(COUPONS_FILE, [])
    now = datetime.now(timezone.utc)
    existing_ids = {f"{c.get('home')}_{c.get('pick')}" for c in coupons}

    for l_key, l_name in LEAGUES.items():
        print(f"[DEBUG] Sprawdzam ligę: {l_name}")
        events = fetch_odds(l_key)

        if not events:
            print(f"[DEBUG] Brak wydarzeń w lidze {l_name}, pomijam...")
            continue  # brak testowych zakładów

        for e in events:
            home, away = e['home_team'], e['away_team']
            dt = parser.isoparse(e["commence_time"])
            if not (now <= dt <= now + timedelta(hours=SCAN_DAYS)): continue

            odds_map = defaultdict(list)
            for bm in e["bookmakers"]:
                for m in bm["markets"]:
                    for o in m["outcomes"]:
                        odds_map[o["name"]].append(o["price"])
            best_odds = {n:max(l) for n,l in odds_map.items() if len(l)>=2}
            if len(best_odds)!=2:
                print(f"[DEBUG] Brak konkurencyjnych kursów | {home}-{away}")
                continue

            inv = {k:1/v for k,v in best_odds.items()}
            s = sum(inv.values())
            probs = {k:v/s for k,v in inv.items()}

            for sel, prob in probs.items():
                o = best_odds[sel]
                edge = (prob - 1/o*TAX_PL)
                if f"{home}_{sel}" in existing_ids: 
                    print(f"[DEBUG] Duplikat | {home}-{away} | {sel}")
                    continue
                if edge >= MIN_EDGE:
                    local_dt = dt.astimezone(timezone(timedelta(hours=1)))
                    date_str = local_dt.strftime("%d.%m o %H:%M")
                    msg = (f"🎯 OKAZJA ({l_name})\n"
                           f"🏟 {home} vs {away}\n"
                           f"⏰ Start: {date_str}\n"
                           f"Typ: {sel}\n"
                           f"Kurs: {o} (NO TAX)\n"
                           f"📈 Edge: +{edge*100:.2f}%\n"
                           f"💰 Stawka: {STAWKA} zł")
                    send_msg(msg)
                    coupons.append({
                        "home":home,
                        "away":away,
                        "pick":sel,
                        "odds":o,
                        "stake":float(STAWKA),
                        "status":"PENDING",
                        "league":l_name,
                        "league_key":l_key,
                        "date":dt.isoformat(),
                        "edge":round(edge*100,2)
                    })
                    existing_ids.add(f"{home}_{sel}")
                    print(f"[DEBUG] ACCEPT {l_name} | {home}-{away} | {sel} | {o} | EDGE {edge*100:.2f}%")
    save_json(COUPONS_FILE, coupons)

if __name__=="__main__":
    run_scanner()