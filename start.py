import requests, json, os
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from dateutil import parser

# ===== CONFIG =====
USE_TAX = False
TAX = 1.0
SCAN_HOURS = 45
MIN_EDGE = 0.005
STAKE = 100

T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")

API_KEYS = [os.getenv(f"ODDS_KEY{i}") for i in ["", "_2", "_3"] if os.getenv(f"ODDS_KEY{i}")]
FILE = "coupons_notax.json"

LEAGUES = {
    "basketball_nba": "🏀 NBA",
    "icehockey_nhl": "🏒 NHL",
    "soccer_poland_ekstraklasa": "⚽ Ekstraklasa"
}

# ===== HELPERS =====
def load():
    if os.path.exists(FILE):
        with open(FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save(data):
    with open(FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def tg(msg):
    if T_TOKEN and T_CHAT:
        requests.post(
            f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
            json={"chat_id": T_CHAT, "text": msg, "parse_mode": "HTML"}
        )

def fetch(league):
    for k in API_KEYS:
        r = requests.get(
            f"https://api.the-odds-api.com/v4/sports/{league}/odds",
            params={"apiKey": k, "markets": "h2h", "regions": "eu"}
        )
        if r.status_code == 200:
            return r.json()
    return []

# ===== MAIN =====
def run():
    coupons = load()
    now = datetime.now(timezone.utc)

    sent_ids = {
        f"{c['home']}_{c['away']}_{c['pick']}_{c['date']}"
        for c in coupons
    }

    for lkey, lname in LEAGUES.items():
        events = fetch(lkey)
        for e in events:
            dt = parser.isoparse(e["commence_time"])
            if not (now <= dt <= now + timedelta(hours=SCAN_HOURS)):
                continue

            odds = defaultdict(list)
            for bm in e["bookmakers"]:
                for o in bm["markets"][0]["outcomes"]:
                    odds[o["name"]].append(o["price"])

            odds = {k: max(v) for k, v in odds.items() if len(v) >= 2}
            if len(odds) != 2:
                continue

            inv = {k: 1 / v for k, v in odds.items()}
            total = sum(inv.values())
            probs = {k: v / total for k, v in inv.items()}

            edges = {k: probs[k] - 1 / (odds[k] * TAX) for k in odds}
            pick, edge = max(edges.items(), key=lambda x: x[1])

            if edge < MIN_EDGE:
                continue

            uid = f"{e['home_team']}_{e['away_team']}_{pick}_{dt.isoformat()}"
            if uid in sent_ids:
                continue

            msg = (
                f"🎯 <b>OKAZJA ({lname})</b>\n"
                f"{e['home_team']} vs {e['away_team']}\n"
                f"⏰ {dt.astimezone(timezone(timedelta(hours=1))).strftime('%d.%m %H:%M')}\n\n"
                f"Typ: <b>{pick}</b>\n"
                f"Kurs: <b>{odds[pick]}</b> (NO TAX)\n"
                f"Edge: <b>+{edge*100:.2f}%</b>\n"
                f"Stawka: <b>{STAKE} zł</b>"
            )

            tg(msg)

            coupons.append({
                "home": e["home_team"],
                "away": e["away_team"],
                "pick": pick,
                "odds": odds[pick],
                "stake": STAKE,
                "league": lname,
                "date": dt.isoformat(),
                "edge": round(edge * 100, 2),
                "status": "PENDING",
                "result": None,
                "profit": 0,
                "notified": False,
                "settled_at": None
            })

            sent_ids.add(uid)

    save(coupons)

if __name__ == "__main__":
    run()