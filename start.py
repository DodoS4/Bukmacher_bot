import os
import json
import requests
from datetime import datetime, timedelta, timezone
import uuid

# ================= KONFIGURACJA =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")           # Kanał ofert
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS") # Kanał wyników

KEYS_POOL = [os.getenv(f"ODDS_KEY{i}") for i in ["", "_2", "_3", "_4", "_5"]]
API_KEYS = [k for k in KEYS_POOL if k]

COUPONS_FILE = "coupons.json"
MAX_DAILY_OFFERS = 20

# ================= POMOCNICZE =================
def load_coupons():
    if not os.path.exists(COUPONS_FILE):
        return []
    with open(COUPONS_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except:
            return []

def save_coupons(coupons):
    with open(COUPONS_FILE, "w", encoding="utf-8") as f:
        json.dump(coupons[-1000:], f, indent=4)

def send_msg(text, target="offers"):
    chat_id = T_CHAT_RESULTS if target == "results" else T_CHAT
    if not chat_id or not T_TOKEN: return
    try:
        requests.post(
            f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
            timeout=15
        )
    except:
        pass

# ================= LOGIKA LIMITÓW =================
def daily_limit_reached(coupons):
    today = datetime.now(timezone.utc).date().isoformat()
    today_sent = [c for c in coupons if c["date"] == today]
    return len(today_sent) >= MAX_DAILY_OFFERS

def match_already_sent(coupons, match_id):
    return any(c["match"]["id"] == match_id for c in coupons)

# ================= TWORZENIE NOWEGO KUPONU =================
def create_coupon(match, pick, stake=100):
    coupons = load_coupons()

    if daily_limit_reached(coupons):
        return False
    if match_already_sent(coupons, match["id"]):
        return False

    implied_prob = 1 / pick["odds"]
    value = pick["model_prob"] - implied_prob
    if value <= 0:
        return False

    coupon = {
        "coupon_id": str(uuid.uuid4()),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "date": datetime.now(timezone.utc).date().isoformat(),
        "status": "pending",
        "sport_key": match.get("sport_key", ""),
        "match": match,
        "pick": {
            "market": pick.get("market", "h2h"),
            "selection": pick["selection"],
            "odds": pick["odds"],
            "model_prob": pick["model_prob"],
            "implied_prob": implied_prob,
            "value": value
        },
        "stake": stake,
        "win_val": round(stake * pick["odds"], 2),
        "result": {
            "final_score": None,
            "winner": None,
            "profit": None
        }
    }

    coupons.append(coupon)
    save_coupons(coupons)

    # wysyłka do kanału ofert
    msg = (
        f"🎯 *NOWA OFERTA*\n"
        f"🏟️ `{match['home']} vs {match['away']}`\n"
        f"💡 Typ: `{pick['selection']}`\n"
        f"📈 Kurs: `{pick['odds']}`\n"
        f"🔥 Value: `{value:.2f}`\n"
        f"💰 Potencjalna wygrana: `{coupon['win_val']} PLN`"
    )
    send_msg(msg, target="offers")
    return True

# ================= ROZLICZANIE =================
def check_results():
    coupons = load_coupons()
    updated = False
    now = datetime.now(timezone.utc)

    for c in coupons:
        if c.get("status") != "pending": continue
        end_time = datetime.fromisoformat(c["match"]["start_time"])
        if now < end_time + timedelta(hours=4): continue  # 4h po meczu

        # Pobranie wyników z API
        s_key = c.get("sport_key")
        for key in API_KEYS:
            try:
                r = requests.get(
                    f"https://api.the-odds-api.com/v4/sports/{s_key}/scores/",
                    params={"apiKey": key, "daysFrom": 3},
                    timeout=15
                )
                if r.status_code != 200: continue
                scores = r.json()
                s_data = next((s for s in scores if s["id"] == c["match"]["id"] and s.get("completed")), None)
                if not s_data: continue

                h_t, a_t = s_data['home_team'], s_data['away_team']
                sl = s_data.get("scores", [])
                h_s = int(next(x['score'] for x in sl if x['name'] == h_t))
                a_s = int(next(x['score'] for x in sl if x['name'] == a_t))

                winner = h_t if h_s > a_s else (a_t if a_s > h_s else "Remis")
                c["status"] = "win" if winner == c["pick"]["selection"] else "loss"
                c["result"]["final_score"] = f"{h_s}:{a_s}"
                c["result"]["winner"] = winner
                c["result"]["profit"] = round(c['win_val'] - c['stake'], 2) if c["status"]=="win" else -c['stake']

                updated = True

                icon = "✅" if c["status"]=="win" else "❌"
                res_text = (
                    f"{icon} *KUPON ROZLICZONY*\n"
                    f"━━━━━━━━━━━━━━━\n"
                    f"🏟️ `{h_t} {h_s}:{a_s} {a_t}`\n"
                    f"🎯 Twój typ: `{c['pick']['selection']}`\n"
                    f"💰 Bilans: `{c['result']['profit']:+.2f} PLN`"
                )
                send_msg(res_text, target="results")
                break
            except:
                continue

    if updated:
        save_coupons(coupons)

# ================= RAPORT TYGODNIOWY =================
def send_weekly_report():
    coupons = load_coupons()
    last_week = datetime.now(timezone.utc) - timedelta(days=7)
    completed = [c for c in coupons if c.get("status") in ["win","loss"]
                 and datetime.fromisoformat(c["match"]["start_time"]) > last_week]
    if not completed: return

    profit = sum(c["result"]["profit"] if c["result"]["profit"] is not None else 0 for c in completed)
    wins = len([c for c in completed if c["status"]=="win"])

    msg = (
        f"📅 *PODSUMOWANIE TYGODNIA*\n━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ Trafione: `{wins}/{len(completed)}`\n"
        f"💰 Zysk/Strata: `{profit:+.2f} PLN` {'🚀' if profit>=0 else '📉'}\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )
    send_msg(msg, target="results")

# ================= SYMULACJA OFERT =================
# Tu podajesz swoje mecze / typy / model probability
def simulate_offers():
    matches = [
        {"id":"m1","sport_key":"soccer_epl","home":"Arsenal","away":"Chelsea","start_time":"2026-01-05T18:00:00+00:00"},
        {"id":"m2","sport_key":"soccer_epl","home":"Liverpool","away":"Man City","start_time":"2026-01-05T20:00:00+00:00"},
    ]
    picks = [
        {"selection":"Arsenal","odds":1.85,"model_prob":0.60,"market":"h2h"},
        {"selection":"Liverpool","odds":2.00,"model_prob":0.55,"market":"h2h"},
    ]

    for m, p in zip(matches, picks):
        create_coupon(m, p, stake=100)

# ================= START =================
def run():
    check_results()        # Rozlicz stare kupony
    simulate_offers()      # Stwórz nowe oferty
    now = datetime.now(timezone.utc)
    if now.weekday()==0 and now.hour==8:  # Poniedziałek 8:00 UTC
        send_weekly_report()

if __name__=="__main__":
    run()
