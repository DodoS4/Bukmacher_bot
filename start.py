import requests, json, os
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from dateutil import parser

# ================= CONFIG =================
USE_TAX = False
TAX_PL = 1.0

MIN_EDGE = 0.005        # 0.5%
STAWKA = 100            # zł
SCAN_HOURS = 45         # 45 godzin do przodu

T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")

API_KEYS = [os.getenv(f"ODDS_KEY{i}") for i in ["", "_2", "_3", "_4", "_5"]]
API_KEYS = [k for k in API_KEYS if k]

COUPONS_FILE = "coupons_notax.json"

# ================= LIGI =================
LEAGUES = {
    "basketball_nba": "🏀 NBA",
    "basketball_euroleague": "🏀 Euroleague",
    "soccer_poland_ekstraklasa": "⚽ Ekstraklasa",
    "soccer_england_championship": "⚽ Championship",
    "icehockey_nhl": "🏒 NHL",
    "tennis_atp_challenger_tour": "🎾 ATP Challenger",
    "esports_csgo_esl_pro_league": "🎮 CS:GO ESL"
}

# ================= HELPERS =================
def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def send_msg(txt):
    if not T_TOKEN or not T_CHAT:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
            json={"chat_id": T_CHAT, "text": txt, "parse_mode": "HTML"}
        )
    except:
        pass

def fetch_odds(league_key):
    for key in API_KEYS:
        r = requests.get(
            f"https://api.the-odds-api.com/v4/sports/{league_key}/odds",
            params={"apiKey": key, "markets": "h2h", "regions": "eu"}
        )
        if r.status_code == 200:
            return r.json()
    return None

# ================= MAIN =================
def run_scanner():
    print(f"🔍 START SKANU: {datetime.now().strftime('%H:%M:%S')}")
    coupons = load_json(COUPONS_FILE, [])
    now = datetime.now(timezone.utc)

    existing = {
        f"{c['home']}_{c['away']}_{c['pick']}_{c['date']}"
        for c in coupons
    }

    debug_low_edge = []
    debug_no_comp = []
    counts = {"sent":0, "dup":0, "checked_leagues":0}

    for l_key, l_name in LEAGUES.items():
        print(f"\n📡 Sprawdzam ligę: {l_name} ({l_key})...")
        counts["checked_leagues"] += 1

        events = fetch_odds(l_key)
        if not events:
            print(f"   ℹ️ Brak ofert w tej lidze.")
            continue

        for e in events:
            home, away = e["home_team"], e["away_team"]
            dt = parser.isoparse(e["commence_time"])
            print(f"   🔹 Sprawdzany mecz: {home} vs {away} | Start: {dt}")

            if not (now <= dt <= now + timedelta(hours=SCAN_HOURS)):
                print(f"      ⏱ Mecz poza zakresem {SCAN_HOURS}h, pomijam.")
                continue

            odds_map = defaultdict(list)
            for bm in e["bookmakers"]:
                for m in bm["markets"]:
                    for o in m["outcomes"]:
                        odds_map[o["name"]].append(o["price"])

            best_odds = {k:max(v) for k,v in odds_map.items() if len(v)>=2}
            if len(best_odds) != 2:
                debug_no_comp.append(f"{home}-{away} ({l_name})")
                print(f"      ⚠️ Brak porównania kursów, pomijam.")
                continue

            # Obliczamy edge dla obu typów
            inv = {k: 1/v for k,v in best_odds.items()}
            s = sum(inv.values())
            probs = {k:v/s for k,v in inv.items()}
            edges = {sel: probs[sel] - 1/(best_odds[sel]*TAX_PL) for sel in probs.keys()}

            # Wybieramy tylko typ z największym edge
            best_type = max(edges.items(), key=lambda x: x[1])
            sel, edge = best_type
            o = best_odds[sel]
            uid = f"{home}_{away}_{sel}_{dt.isoformat()}"

            if uid in existing:
                counts["dup"] += 1
                print(f"      ♻️ Duplikat: {sel} ({home}-{away})")
                continue

            if edge >= MIN_EDGE:
                local_dt = dt.astimezone(timezone(timedelta(hours=1)))
                date_str = local_dt.strftime("%d.%m %H:%M")
                msg = (f"🎯 OKAZJA ({l_name})\n"
                       f"{home} vs {away}\n"
                       f"⏰ Start: {date_str}\n"
                       f"Typ: {sel} | Kurs: {o} | Edge: {edge*100:.2f}%\n"
                       f"Stawka: {STAWKA} zł")
                send_msg(msg)
                coupons.append({"home":home,"away":away,"pick":sel,"odds":o,"stake":STAWKA,
                                "status":"PENDING","league_key":l_key,"league_name":l_name,
                                "date":dt.isoformat(),"edge":round(edge*100,2)})
                existing.add(uid)
                counts["sent"] += 1
                print(f"      ✅ Wyślij typ: {sel} | Edge: {edge*100:.2f}%")
            else:
                debug_low_edge.append(f"{home}-{away} ({sel}) | Edge: {edge*100:.2f}%")
                print(f"      ❌ Edge za niski: {edge*100:.2f}% | Pomijam")

    save_json(COUPONS_FILE, coupons)

    print("\n" + "="*50)
    print("📊 PODSUMOWANIE SKANU")
    print(f"✅ Wysłano: {counts['sent']} | ♻️ Duplikaty: {counts['dup']}")
    print(f"⚠️ Brak porównania: {len(debug_no_comp)} | ❌ Odrzucono (Edge): {len(debug_low_edge)}")
    print("="*50 + "\n")

if __name__ == "__main__":
    run_scanner()