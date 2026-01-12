import requests, json, os
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from dateutil import parser

# ================= CONFIG =================
USE_TAX = False
TAX_PL = 1.0                # NO TAX
MIN_EDGE = 0.005            # 0.5%
STAWKA = 100                # zł
SCAN_HOURS = 45             # 45 godzin do przodu

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
            json={
                "chat_id": T_CHAT,
                "text": txt,
                "parse_mode": "HTML"
            }
        )
    except Exception as e:
        print(f"⚠️ Telegram error: {e}")

def fetch_odds(league_key):
    for key in API_KEYS:
        r = requests.get(
            f"https://api.the-odds-api.com/v4/sports/{league_key}/odds",
            params={
                "apiKey": key,
                "markets": "h2h",
                "regions": "eu"
            }
        )
        if r.status_code == 200:
            return r.json()
    return None

# ================= MAIN =================
def run_scanner():
    print(f"\n🔍 START SKANU: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    coupons = load_json(COUPONS_FILE, [])
    now = datetime.now(timezone.utc)

    existing_ids = {
        f"{c['home']}_{c['away']}_{c['pick']}_{c['date']}"
        for c in coupons
    }

    stats = {
        "checked_leagues": 0,
        "checked_matches": 0,
        "sent": 0,
        "duplicates": 0,
        "low_edge": 0,
        "no_compare": 0
    }

    for l_key, l_name in LEAGUES.items():
        print(f"\n📡 Liga: {l_name}")
        stats["checked_leagues"] += 1

        events = fetch_odds(l_key)
        if not events:
            print("   ℹ️ Brak danych odds")
            continue

        for e in events:
            stats["checked_matches"] += 1

            home, away = e["home_team"], e["away_team"]
            dt = parser.isoparse(e["commence_time"])

            print(f"   ▶ {home} vs {away} | {dt}")

            if not (now <= dt <= now + timedelta(hours=SCAN_HOURS)):
                print("      ⏱ Poza zakresem 45h")
                continue

            odds_map = defaultdict(list)
            for bm in e.get("bookmakers", []):
                for m in bm.get("markets", []):
                    for o in m.get("outcomes", []):
                        odds_map[o["name"]].append(o["price"])

            best_odds = {k: max(v) for k, v in odds_map.items() if len(v) >= 2}

            if len(best_odds) != 2:
                stats["no_compare"] += 1
                print("      ⚠️ Brak porównania kursów")
                continue

            inv = {k: 1 / v for k, v in best_odds.items()}
            total = sum(inv.values())
            probs = {k: v / total for k, v in inv.items()}

            edges = {
                sel: probs[sel] - 1 / (best_odds[sel] * TAX_PL)
                for sel in probs
            }

            sel, edge = max(edges.items(), key=lambda x: x[1])
            o = best_odds[sel]

            uid = f"{home}_{away}_{sel}_{dt.isoformat()}"
            if uid in existing_ids:
                stats["duplicates"] += 1
                print("      ♻️ Duplikat")
                continue

            if edge < MIN_EDGE:
                stats["low_edge"] += 1
                print(f"      ❌ Edge za niski: {edge*100:.2f}%")
                continue

            local_dt = dt.astimezone(timezone(timedelta(hours=1)))
            date_str = local_dt.strftime("%d.%m %H:%M")

            msg = (
                f"🎯 <b>OKAZJA ({l_name})</b>\n"
                f"{home} vs {away}\n"
                f"⏰ {date_str}\n\n"
                f"Typ: <b>{sel}</b>\n"
                f"Kurs: <b>{o}</b> (NO TAX)\n"
                f"Edge: <b>+{edge*100:.2f}%</b>\n"
                f"Stawka: <b>{STAWKA} zł</b>"
            )

            send_msg(msg)

            coupons.append({
                "home": home,
                "away": away,
                "pick": sel,
                "odds": o,
                "stake": STAWKA,
                "status": "PENDING",
                "notified": False,
                "settled_at": None,
                "league_key": l_key,
                "league_name": l_name,
                "date": dt.isoformat(),
                "edge": round(edge * 100, 2)
            })

            existing_ids.add(uid)
            stats["sent"] += 1
            print(f"      ✅ Wysłano | Edge {edge*100:.2f}%")

    save_json(COUPONS_FILE, coupons)

    print("\n" + "=" * 60)
    print("📊 PODSUMOWANIE")
    for k, v in stats.items():
        print(f"{k}: {v}")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    run_scanner()