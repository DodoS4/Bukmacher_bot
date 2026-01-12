import requests, json, os
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from dateutil import parser

# ===== CONFIG =====
TAX = 1.0           # NO TAX
SCAN_HOURS = 45
MIN_EDGE = 0.005     # 0.5%
STAKE = 100
DEBUG = True

T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")
API_KEYS = [os.getenv(f"ODDS_KEY{i}") for i in ["", "_2", "_3", "_4", "_5"] if os.getenv(f"ODDS_KEY{i}")]
FILE = "coupons_notax.json"

# ===== LIGI =====
LEAGUES = {
    # 🏀 Koszykówka
    "basketball_nba": "🏀 NBA",
    "basketball_euroleague": "🏀 Euroleague",
    "basketball_spain_liga_acb": "🏀 Hiszpania ACB",
    "basketball_germany_bbl": "🏀 Niemcy BBL",

    # ⚽ Piłka nożna
    "soccer_england_premier_league": "⚽ Premier League",
    "soccer_england_championship": "⚽ Anglia Championship",
    "soccer_england_league1": "⚽ Anglia L1",
    "soccer_italy_serie_a": "⚽ Serie A",
    "soccer_italy_serie_b": "⚽ Serie B",
    "soccer_spain_la_liga": "⚽ La Liga",
    "soccer_germany_bundesliga": "⚽ Bundesliga",
    "soccer_germany_bundesliga2": "⚽ Bundesliga 2",
    "soccer_poland_ekstraklasa": "⚽ Ekstraklasa",

    # 🎾 Tenis
    "tennis_atp_1000": "🎾 ATP 1000",
    "tennis_atp_challenger_tour": "🎾 ATP Challenger",
    "tennis_wta_1000": "🎾 WTA 1000",

    # 🏒 Hokej
    "icehockey_nhl": "🏒 NHL",
    "icehockey_sweden_allsvenskan": "🏒 Szwecja Allsvenskan",
    "icehockey_finland_liiga": "🏒 Finlandia Liiga",

    # 🎮 Esport
    "esports_csgo_blast_premier": "🎮 CS:GO BLAST",
    "esports_csgo_esl_pro_league": "🎮 CS:GO ESL Pro",
    "esports_league_of_legends_lck": "🎮 LoL LCK",
    "esports_league_of_legends_lpl": "🎮 LoL LPL",

    # 🏐 Siatkówka
    "volleyball_poland_plusliga": "🏐 PlusLiga (PL)",
    "volleyball_italy_superlega": "🏐 Siatkówka Włochy"
}

# ===== HELPERS =====
def load():
    if os.path.exists(FILE):
        with open(FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except:
                return []
    return []

def save(data):
    with open(FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def tg(msg):
    if T_TOKEN and T_CHAT:
        try:
            requests.post(
                f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
                json={"chat_id": T_CHAT, "text": msg, "parse_mode": "HTML"}
            )
        except:
            pass

def log(msg):
    if DEBUG:
        print(f"[DEBUG] {msg}")

def fetch(league):
    for key in API_KEYS:
        try:
            r = requests.get(
                f"https://api.the-odds-api.com/v4/sports/{league}/odds",
                params={"apiKey": key, "markets": "h2h", "regions": "eu"}
            )
            if r.status_code == 200:
                return r.json()
        except:
            continue
    return []

# ===== MAIN =====
def run():
    coupons = load()
    now = datetime.now(timezone.utc)
    sent_ids = {f"{c['home']}_{c['away']}_{c['pick']}_{c['date']}" for c in coupons}

    for lkey, lname in LEAGUES.items():
        events = fetch(lkey)
        if not events:
            log(f"{lname}: brak wydarzeń")
            continue

        for e in events:
            dt = parser.isoparse(e["commence_time"])
            if not (now <= dt <= now + timedelta(hours=SCAN_HOURS)):
                log(f"REJECT TIME | {e['home_team']}-{e['away_team']}")
                continue

            odds_map = defaultdict(list)
            for bm in e.get("bookmakers", []):
                for m in bm.get("markets", []):
                    for o in m.get("outcomes", []):
                        odds_map[o["name"]].append(o["price"])

            best_odds = {k: max(v) for k, v in odds_map.items() if len(v) >= 2}
            if len(best_odds) != 2:
                log(f"REJECT BOOKS | {e['home_team']}-{e['away_team']}")
                continue

            inv = {k: 1/v for k, v in best_odds.items()}
            total = sum(inv.values())
            probs = {k: v/total for k, v in inv.items()}
            edges = {k: probs[k] - 1/(best_odds[k]*TAX) for k in best_odds}

            pick, edge = max(edges.items(), key=lambda x: x[1])

            uid = f"{e['home_team']}_{e['away_team']}_{pick}_{dt.isoformat()}"
            if uid in sent_ids:
                log(f"REJECT DUPLICATE | {e['home_team']}-{e['away_team']} | {pick}")
                continue

            if edge < MIN_EDGE:
                log(f"REJECT EDGE {edge*100:.2f}% < {MIN_EDGE*100:.2f}% | {e['home_team']}-{e['away_team']} | {pick}")
                continue

            # Dodanie zakładu i zapis natychmiast
            coupons.append({
                "home": e["home_team"],
                "away": e["away_team"],
                "pick": pick,
                "odds": best_odds[pick],
                "stake": STAKE,
                "league": lname,
                "date": dt.isoformat(),
                "edge": round(edge*100, 2),
                "status": "PENDING",
                "result": None,
                "profit": 0,
                "notified": True,
                "settled_at": None
            })
            sent_ids.add(uid)

            with open(FILE, "w", encoding="utf-8") as f:
                json.dump(coupons, f, indent=2)

            # Telegram
            msg = (
                f"🎯 <b>OKAZJA ({lname})</b>\n"
                f"{e['home_team']} vs {e['away_team']}\n"
                f"⏰ {dt.astimezone(timezone(timedelta(hours=1))).strftime('%d.%m %H:%M')}\n\n"
                f"Typ: <b>{pick}</b>\n"
                f"Kurs: <b>{best_odds[pick]}</b> (NO TAX)\n"
                f"Edge: <b>+{edge*100:.2f}%</b>\n"
                f"Stawka: <b>{STAKE} zł</b>"
            )
            tg(msg)
            log(f"ACCEPT {lname} | {e['home_team']}-{e['away_team']} | {pick} | {best_odds[pick]} | EDGE {edge*100:.2f}%")

    log("SCAN COMPLETE")

if __name__ == "__main__":
    run()