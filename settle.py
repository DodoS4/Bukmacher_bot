import os
import json
import requests
from datetime import datetime, timezone, timedelta

# ================= KONFIGURACJA =================
COUPONS_FILE = "coupons.json"
HISTORY_FILE = "history.json"
STATS_JSON_FILE = "stats.json"

# ================= POMOCNICZE =================
def get_secret(name):
    val = os.environ.get(name) or os.getenv(name)
    return str(val).strip() if val else None

def send_telegram_results(message):
    token = get_secret("T_TOKEN")
    chat = get_secret("T_CHAT_RESULTS") or get_secret("T_CHAT")
    if not token or not chat:
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=15)
    except:
        pass

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
        params = {"apiKey": key, "daysFrom": 3} # NHL/Soccer wyniki są dostępne szybko
        try:
            r = requests.get(url, params=params, timeout=15)
            if r.status_code == 200:
                return r.json()
        except:
            continue
    return None

# ================= RAPORT / DASHBOARD =================
def generate_report(history, remaining_count):
    now = datetime.now(timezone.utc)
    base_capital = 1000.0
    
    if os.path.exists(STATS_JSON_FILE):
        try:
            with open(STATS_JSON_FILE, "r") as f:
                current_stats = json.load(f)
                if not any(m.get("status") != "ARCHIVED" for m in history):
                    base_capital = current_stats.get("bankroll", 1000.0)
        except:
            pass

    total_profit_new = 0.0
    current_offset = 0.0
    total_staked_new = 0.0
    profit_24h = 0.0
    graph_data = [base_capital]

    history_sorted = sorted(history, key=lambda x: x.get("time", ""))

    for m in history_sorted:
        if m.get("status") == "ARCHIVED":
            continue
            
        profit = float(m.get("profit", 0))
        stake = float(m.get("stake", 0))
        is_finance = m.get("sport") == "FINANCE"

        current_offset += profit
        graph_data.append(round(base_capital + current_offset, 2))

        if not is_finance:
            total_profit_new += profit
            total_staked_new += stake
            t = m.get("time")
            if t:
                try:
                    mt = datetime.fromisoformat(t.replace("Z", "+00:00"))
                    if now - mt < timedelta(hours=24):
                        profit_24h += profit
                except:
                    pass

    bankroll = base_capital + current_offset
    yield_val = (total_profit_new / total_staked_new * 100) if total_staked_new > 0 else 0

    stats = {
        "bankroll": round(bankroll, 2),
        "zysk_total": round(total_profit_new, 2),
        "zysk_24h": round(profit_24h, 2),
        "obrot": round(total_staked_new, 2),
        "yield": round(yield_val, 2),
        "last_sync": now.strftime("%d.%m.%Y %H:%M"),
        "upcoming_val": remaining_count,
        "history_graph": graph_data[-100:]
    }

    with open(STATS_JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=4)

    active_history = [m for m in history if m.get("status") in ["WIN", "LOSS"]]
    wins = sum(1 for m in active_history if m.get("status") == "WIN")
    total = len(active_history)
    accuracy = (wins / total * 100) if total > 0 else 0

    msg = [
        "🔄 <b>SYSTEM RESTARTED</b>" if total == 0 else "📊 <b>DASHBOARD UPDATED</b>",
        f"🏦 Bankroll: <b>{round(bankroll,2)} PLN</b>",
        f"💰 Nowy Zysk: {round(total_profit_new,2)} PLN",
        f"📈 Yield: {round(yield_val,2)}% | Celność: {round(accuracy,1)}%",
        "━━━━━━━━━━━━━━━",
        "📝 <b>OSTATNIE (NOWE):</b>"
    ]

    recent_active = [m for m in history if m.get("status") != "ARCHIVED"][-5:]
    for m in reversed(recent_active):
        if m.get("sport") == "FINANCE":
            icon, name = "🏦", "OPERACJA FINANSOWA"
        else:
            icon = "✅" if m.get("status") == "WIN" else "❌" if m.get("status") == "LOSS" else "⚪"
            name = f"{m.get('home')} - {m.get('away')}"
        msg.append(f"{icon} {name} ({m.get('profit')} PLN)")

    send_telegram_results("\n".join(msg))

# ================= SETTLEMENT =================
def settle_matches():
    api_keys = get_all_api_keys()
    if not api_keys or not os.path.exists(COUPONS_FILE):
        return

    with open(COUPONS_FILE, "r", encoding="utf-8") as f:
        active_coupons = json.load(f)

    if not active_coupons:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
            generate_report(history, 0)
        return

    history = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
        except:
            pass

    history_ids = {h.get("id") for h in history if h.get("id")}
    results_map = {}
    remaining = []
    new_settlements = 0

    sports = list(set(c["sport"] for c in active_coupons))
    for sport in sports:
        res = get_match_results(sport, api_keys)
        if res:
            for m in res:
                if m.get("id"):
                    results_map[m["id"]] = m

    for c in active_coupons:
        cid = c.get("id")
        if cid in history_ids:
            continue

        match = results_map.get(cid)
        if match and match.get("completed"):
            scores = {s["name"]: int(s.get("score", 0)) for s in match.get("scores", [])}
            home, away = match.get("home_team"), match.get("away_team")
            hs, as_ = scores.get(home, 0), scores.get(away, 0)
            total_score = hs + as_

            status = "LOSS"
            stake = float(c.get("stake", 0))
            
            # --- LOGIKA ROZLICZANIA ---
            market_type = c.get("market_type", "h2h")
            outcome = c.get("outcome", "")

            if market_type == "h2h":
                if hs == as_:
                    status = "VOID"
                elif (outcome == home and hs > as_) or (outcome == away and as_ > hs):
                    status = "WIN"
            
            elif market_type == "totals":
                try:
                    # outcome to np. "Over 5.5" lub "Under 2.5"
                    parts = outcome.split()
                    condition = parts[0] # Over / Under
                    line = float(parts[1]) # 5.5
                    
                    if condition == "Over" and total_score > line:
                        status = "WIN"
                    elif condition == "Under" and total_score < line:
                        status = "WIN"
                    elif total_score == line: # Bardzo rzadkie, ale możliwe przy liniach całkowitych
                        status = "VOID"
                except:
                    status = "LOSS"

            # Obliczanie profitu
            if status == "WIN":
                profit = round(stake * float(c.get("odds", 0)) - stake, 2)
            elif status == "VOID":
                profit = 0.0
            else:
                profit = -stake

            history.append({**c, "profit": profit, "status": status, "score": f"{hs}:{as_}"})
            history_ids.add(cid)
            new_settlements += 1
        else:
            remaining.append(c)

    if new_settlements > 0:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=4)
        with open(COUPONS_FILE, "w", encoding="utf-8") as f:
            json.dump(remaining, f, indent=4)

    generate_report(history, len(remaining))

if __name__ == "__main__":
    settle_matches()
