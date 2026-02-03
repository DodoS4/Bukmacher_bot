import os
import json
import requests
from datetime import datetime, timezone

COUPONS_FILE = "coupons.json"
HISTORY_FILE = "history.json"
STATS_JSON_FILE = "stats.json"

# ================== POMOCNICZE ==================
def get_secret(name):
    return os.environ.get(name)

def send_telegram(msg):
    token = get_secret("T_TOKEN")
    chat = get_secret("T_CHAT_RESULTS") or get_secret("T_CHAT")
    if not token or not chat:
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    requests.post(url, json={"chat_id": chat, "text": msg})

def get_all_api_keys():
    keys = []
    for i in range(1, 11):
        k = os.getenv("ODDS_KEY" if i == 1 else f"ODDS_KEY_{i}")
        if k:
            keys.append(k)
    return keys

def get_results(sport, keys):
    for k in keys:
        url = f"https://api.the-odds-api.com/v4/sports/{sport}/scores/"
        params = {"apiKey": k, "daysFrom": 3}
        try:
            r = requests.get(url, params=params, timeout=15)
            if r.status_code == 200:
                return r.json()
        except:
            pass
    return []

# ================== SETTLE ==================
def settle():
    if not os.path.exists(COUPONS_FILE):
        send_telegram("🧮 ROZLICZANIE | Brak kuponów w grze")
        return

    coupons = json.load(open(COUPONS_FILE))
    history = json.load(open(HISTORY_FILE)) if os.path.exists(HISTORY_FILE) else []

    history_ids = {h["id"] for h in history}
    api_keys = get_all_api_keys()

    results_map = {}
    remaining = []
    settled = []

    sports = list(set(c["sport"] for c in coupons))
    for sport in sports:
        for m in get_results(sport, api_keys):
            if m.get("id"):
                results_map[m["id"]] = m

    debug_log = []
    debug_log.append(f"🧮 ROZLICZANIE MECZÓW | Kupony w grze: {len(coupons)}")

    for c in coupons:
        cid = c["id"]

        if cid in history_ids:
            continue

        match = results_map.get(cid)
        if not match or not match.get("completed"):
            remaining.append(c)
            continue

        home = match["home_team"]
        away = match["away_team"]

        scores = {s["name"]: int(s.get("score", 0)) for s in match.get("scores", [])}
        hs = scores.get(home, 0)
        as_ = scores.get(away, 0)
        total = hs + as_

        market = c["market_type"]
        outcome = c["outcome"]
        stake = float(c["stake"])
        odds = float(c["odds"])

        status = "LOSS"

        # ========== H2H ==========
        if market == "h2h":
            if hs == as_:
                status = "VOID"
            elif outcome == home and hs > as_:
                status = "WIN"
            elif outcome == away and as_ > hs:
                status = "WIN"

        # ========== TOTALS ==========
        elif market == "totals":
            try:
                side, line = outcome.split()
                line = float(line)
                if side == "Over" and total > line:
                    status = "WIN"
                elif side == "Under" and total < line:
                    status = "WIN"
                elif total == line:
                    status = "VOID"
            except:
                status = "LOSS"

        # ========== BTTS ==========
        elif market == "btts":
            if outcome == "Yes" and hs > 0 and as_ > 0:
                status = "WIN"

        # ========== DOUBLE CHANCE ==========
        elif market == "double_chance":
            if outcome == "1X" and hs >= as_:
                status = "WIN"
            elif outcome == "X2" and as_ >= hs:
                status = "WIN"

        # ========== PROFIT ==========
        if status == "WIN":
            profit = round((stake * 0.88) * odds - stake, 2)
        elif status == "VOID":
            profit = 0.0
        else:
            profit = -stake

        entry = {
            **c,
            "status": status,
            "profit": profit,
            "score": f"{hs}:{as_}",
            "settled_at": datetime.now(timezone.utc).isoformat()
        }

        history.append(entry)
        settled.append(entry)
        history_ids.add(cid)

        icon = "✅" if status == "WIN" else "❌" if status == "LOSS" else "➖"
        emoji = "🏒" if "icehockey" in c["sport"] else "⚽"

        debug_log.append(
            f"{emoji} {home} vs {away} — {outcome} {icon} ({profit} PLN)"
        )

    # ================== ZAPIS ==================
    json.dump(history, open(HISTORY_FILE, "w"), indent=4)
    json.dump(remaining, open(COUPONS_FILE, "w"), indent=4)

    # ================== PODSUMOWANIE ==================
    if settled:
        total_profit = round(sum(x["profit"] for x in settled), 2)
        debug_log.append("━━━━━━━━━━━━━━━━━━")
        debug_log.append(f"📊 Rozliczono: {len(settled)}")
        debug_log.append(f"💰 Wynik: {total_profit} PLN")
    else:
        debug_log.append("ℹ️ Brak meczów do rozliczenia")

    send_telegram("\n".join(debug_log))


if __name__ == "__main__":
    settle()
