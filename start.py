import requests, json, os
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from dateutil import parser

# ================= CONFIG =================
USE_TAX = False
TAX_PL = 1.0

MIN_EDGE = 0.005        # 0.5%
STAWKA = 100            # zł
SCAN_HOURS = 45         # <<< 45 godzin

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
    coupons = load_json(COUPONS_FILE, [])
    now = datetime.now(timezone.utc)

    existing = {
        f"{c['home']}_{c['away']}_{c['pick']}_{c['date']}"
        for c in coupons
    }

    for l_key, l_name in LEAGUES.items():
        events = fetch_odds(l_key)
        if not events:
            continue

        for e in events:
            home, away = e["home_team"], e["away_team"]
            dt = parser.isoparse(e["commence_time"])

            if not (now <= dt <= now + timedelta(hours=SCAN_HOURS)):
                continue

            odds_map = defaultdict(list)
            for bm in e["bookmakers"]:
                for m in bm["markets"]:
                    for o in m["outcomes"]:
                        odds_map[o["name"]].append(o["price"])

            best_odds = {k: max(v) for k, v in odds_map.items() if len(v) >= 2}
            if len(best_odds) != 2:
                continue

            inv = {k: 1 / v for k, v in best_odds.items()}
            s = sum(inv.values())
            probs = {k: v / s for k, v in inv.items()}

            for sel, prob in probs.items():
                o = best_odds[sel]
                edge = prob - 1 / (o * TAX_PL)

                uid = f"{home}_{away}_{sel}_{dt.isoformat()}"
                if uid in existing or edge < MIN_EDGE:
                    continue

                txt = (
                    f"🎯 <b>OKAZJA ({l_name})</b>\n"
                    f"{home} vs {away}\n"
                    f"⏰ {dt.astimezone(timezone(timedelta(hours=1))).strftime('%d.%m %H:%M')}\n\n"
                    f"Typ: <b>{sel}</b>\n"
                    f"Kurs: <b>{o}</b> (NO TAX)\n"
                    f"Edge: <b>+{edge*100:.2f}%</b>\n"
                    f"Stawka: <b>{STAWKA} zł</b>"
                )
                send_msg(txt)

                coupons.append({
                    "home": home,
                    "away": away,
                    "pick": sel,
                    "odds": o,
                    "stake": STAWKA,
                    "status": "PENDING",
                    "league_key": l_key,
                    "date": dt.isoformat(),
                    "edge": round(edge * 100, 2)
                })
                existing.add(uid)

    save_json(COUPONS_FILE, coupons)

if __name__ == "__main__":
    run_scanner()