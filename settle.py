import os
import json
import requests
from datetime import datetime, timezone, timedelta

# ================= KONFIGURACJA =================
DEBUG = True

COUPONS_FILE = "coupons.json"
HISTORY_FILE = "history.json"
STATS_JSON_FILE = "stats.json"

# ================= POMOCNICZE =================
def debug(msg):
    if DEBUG:
        print(msg)

def get_secret(name):
    val = os.environ.get(name) or os.getenv(name)
    return str(val).strip() if val else None

def send_telegram_results(message):
    token = get_secret("T_TOKEN")
    chat = get_secret("T_CHAT_RESULTS") or get_secret("T_CHAT")

    if not token or not chat:
        debug("❌ Brak Telegram token / chat_id")
        return

    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": chat,
                "text": message,
                "parse_mode": "HTML"
            },
            timeout=15
        )
    except Exception as e:
        debug(f"❌ Telegram error: {e}")

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
        try:
            r = requests.get(
                f"https://api.the-odds-api.com/v4/sports/{sport}/scores/",
                params={"apiKey": key, "daysFrom": 5},
                timeout=15
            )
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            debug(f"❌ Scores API error: {e}")
    return None

# ================= SETTLEMENT =================
def settle_matches():
    api_keys = get_all_api_keys()
    if not api_keys:
        debug("❌ Brak kluczy API")
        return

    if not os.path.exists(COUPONS_FILE):
        debug("📭 Brak aktywnych kuponów")
        return

    active_coupons = json.load(open(COUPONS_FILE, "r", encoding="utf-8"))
    if not active_coupons:
        debug("📭 Brak aktywnych kuponów")
        return

    history = []
    if os.path.exists(HISTORY_FILE):
        history = json.load(open(HISTORY_FILE, "r", encoding="utf-8"))

    # 🔒 BLOKADA DUPLIKATÓW PO (ID + MARKET + OUTCOME)
    history_keys = {
        (h.get("id"), h.get("market"), h.get("outcome"))
        for h in history
    }

    results_map = {}
    remaining = []
    new_settlements = 0

    sports = list({c["sport"] for c in active_coupons})

    for sport in sports:
        debug(f"📥 Pobieranie wyników: {sport}")
        res = get_match_results(sport, api_keys)
        if res:
            for m in res:
                if m.get("id"):
                    results_map[m["id"]] = m

    for c in active_coupons:
        cid = c.get("id")
        market = c.get("market")
        outcome = c.get("outcome")

        settle_key = (cid, market, outcome)

        if settle_key in history_keys:
            debug(f"🔁 Już rozliczony: {settle_key}")
            continue

        match = results_map.get(cid)

        if not match:
            debug(f"⏳ Brak wyniku meczu: {cid}")
            remaining.append(c)
            continue

        if not match.get("completed"):
            debug(f"⏳ Mecz nieukończony: {cid}")
            remaining.append(c)
            continue

        scores = {
            s["name"]: int(s.get("score", 0))
            for s in (match.get("scores") or [])
        }

        home = match.get("home_team")
        away = match.get("away_team")
        hs = scores.get(home, 0)
        as_ = scores.get(away, 0)
        total_goals = hs + as_

        stake = float(c.get("stake", 0))
        odds = float(c.get("odds", 0))

        status = "LOSS"
        profit = -stake
        reason = "przegrany typ"

        # ===== H2H =====
        if market == "h2h":
            if hs == as_:
                status = "VOID"
                profit = 0.0
                reason = "remis (VOID)"
            elif outcome == home and hs > as_:
                status = "WIN"
                reason = "home win"
            elif outcome == away and as_ > hs:
                status = "WIN"
                reason = "away win"

        # ===== TOTALS =====
        elif market == "totals":
            try:
                direction, line = outcome.split()
                line = float(line)

                if direction == "Over" and total_goals > line:
                    status = "WIN"
                    reason = f"over {line}"
                elif direction == "Under" and total_goals < line:
                    status = "WIN"
                    reason = f"under {line}"
                else:
                    reason = f"total {total_goals} vs {line}"
            except:
                reason = "błędny format totals"

        # ===== BTTS =====
        elif market == "btts":
            both = hs > 0 and as_ > 0
            if outcome == "Yes" and both:
                status = "WIN"
                reason = "BTTS yes"
            elif outcome == "No" and not both:
                status = "WIN"
                reason = "BTTS no"
            else:
                reason = f"BTTS mismatch ({hs}:{as_})"

        if status == "WIN":
            profit = round(stake * odds - stake, 2)

        debug(
            f"🧾 {home} vs {away} | {market} | {outcome} "
            f"=> {status} ({reason})"
        )

        history.append({
            **c,
            "status": status,
            "profit": round(profit, 2),
            "score": f"{hs}:{as_}"
        })

        history_keys.add(settle_key)
        new_settlements += 1

    if new_settlements > 0:
        json.dump(history, open(HISTORY_FILE, "w", encoding="utf-8"), indent=4)
        json.dump(remaining, open(COUPONS_FILE, "w", encoding="utf-8"), indent=4)

        debug(f"✅ Rozliczono: {new_settlements}")
    else:
        debug("ℹ️ Brak nowych rozliczeń")

# ================= ENTRY =================
if __name__ == "__main__":
    settle_matches()
