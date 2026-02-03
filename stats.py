import os
import json
import requests
from datetime import datetime, timezone, timedelta

# ================= KONFIG =================
COUPONS_FILE = "coupons.json"
HISTORY_FILE = "history.json"
STATS_JSON_FILE = "stats.json"

DEBUG = True          # <<< WŁĄCZ / WYŁĄCZ DEBUG
DEBUG_TELEGRAM = False  # <<< jeśli chcesz debug na TG

# ================= POMOC =================
def get_secret(name):
    val = os.environ.get(name)
    return str(val).strip() if val else None

def debug(msg):
    if DEBUG:
        print(msg)
        if DEBUG_TELEGRAM:
            send_telegram_results(f"🛠 DEBUG\n{msg}")

def send_telegram_results(message):
    token = get_secret("T_TOKEN")
    chat = get_secret("T_CHAT_RESULTS") or get_secret("T_CHAT")
    if not token or not chat:
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print("Telegram error:", e)

def get_all_api_keys():
    keys = []
    for i in range(1, 11):
        name = "ODDS_KEY" if i == 1 else f"ODDS_KEY_{i}"
        val = os.getenv(name)
        if val:
            keys.append(val)
    return keys

def get_match_results(sport, keys):
    for key in keys:
        url = f"https://api.the-odds-api.com/v4/sports/{sport}/scores/"
        params = {"apiKey": key, "daysFrom": 5}
        try:
            r = requests.get(url, params=params, timeout=15)
            if r.status_code == 200:
                debug(f"📥 Pobieranie wyników: {sport}")
                return r.json()
        except Exception as e:
            debug(f"❌ API error ({sport}): {e}")
    return []

# ================= RAPORT =================
def generate_report(history, remaining_count):
    now = datetime.now(timezone.utc)
    base_capital = 5000.0

    total_profit = sum(float(m.get("profit", 0)) for m in history)
    total_staked = sum(float(m.get("stake", 0)) for m in history)
    bankroll = base_capital + total_profit

    stats = {
        "bankroll": round(bankroll, 2),
        "zysk_total": round(total_profit, 2),
        "obrot": round(total_staked, 2),
        "last_sync": now.strftime("%d.%m.%Y %H:%M"),
        "upcoming_val": remaining_count
    }

    with open(STATS_JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=4)

# ================= SETTLE =================
def settle_matches():
    api_keys = get_all_api_keys()
    if not api_keys:
        debug("❌ Brak API keys")
        return

    if not os.path.exists(COUPONS_FILE):
        debug("❌ Brak coupons.json")
        return

    active = json.load(open(COUPONS_FILE, "r", encoding="utf-8"))
    history = json.load(open(HISTORY_FILE, "r", encoding="utf-8")) if os.path.exists(HISTORY_FILE) else []

    history_ids = {h["id"] for h in history if "id" in h}
    results_map = {}
    remaining = []
    new = 0

    sports = list({c["sport"] for c in active})

    for sport in sports:
        for m in get_match_results(sport, api_keys):
            if m.get("id"):
                results_map[m["id"]] = m

    for c in active:
        cid = c["id"]

        if cid in history_ids:
            debug(f"⏭️ Pominięty (już w history): {cid}")
            continue

        match = results_map.get(cid)

        if not match:
            debug(f"⏳ Brak meczu w API: {cid}")
            remaining.append(c)
            continue

        if not match.get("completed"):
            debug(f"⏳ Mecz nie zakończony: {cid}")
            remaining.append(c)
            continue

        scores = {s["name"]: int(s.get("score", 0)) for s in match.get("scores", [])}
        home = match.get("home_team")
        away = match.get("away_team")
        hs = scores.get(home, 0)
        as_ = scores.get(away, 0)

        outcome = c.get("outcome")
        stake = float(c.get("stake", 0))
        odds = float(c.get("odds", 0))

        # ===== H2H LOGIKA =====
        if hs == as_:
            status = "VOID"
            profit = 0.0
            reason = "REMIS"
        elif outcome == home and hs > as_:
            status = "WIN"
            profit = round(stake * odds - stake, 2)
            reason = "HOME WYGRAL"
        elif outcome == away and as_ > hs:
            status = "WIN"
            profit = round(stake * odds - stake, 2)
            reason = "AWAY WYGRAL"
        else:
            status = "LOSS"
            profit = -stake
            reason = f"PRZEGRANA ({hs}:{as_})"

        debug(f"🧾 {home} vs {away} | typ: {outcome} | wynik: {hs}:{as_} → {status} ({reason})")

        history.append({
            **c,
            "status": status,
            "profit": profit,
            "score": f"{hs}:{as_}",
            "settled_at": datetime.now(timezone.utc).isoformat()
        })

        history_ids.add(cid)
        new += 1

    if new == 0:
        debug("ℹ️ Brak nowych rozliczeń")

    json.dump(history, open(HISTORY_FILE, "w", encoding="utf-8"), indent=4)
    json.dump(remaining, open(COUPONS_FILE, "w", encoding="utf-8"), indent=4)

    generate_report(history, len(remaining))

# ================= ENTRY =================
if __name__ == "__main__":
    settle_matches()
