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
    payload = {
        "chat_id": chat,
        "text": message,
        "parse_mode": "HTML"
    }
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
        params = {
            "apiKey": key,
            "daysFrom": 5
        }
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
    base_capital = 5000.0

    current_balance_offset = 0.0  # Wszystko (Mecze + Wypłaty)
    betting_profit_total = 0.0    # Tylko mecze
    total_staked = 0.0            # Tylko mecze
    profit_24h = 0.0              # Tylko mecze z 24h
    graph_data = [base_capital]

    history_sorted = sorted(history, key=lambda x: x.get("time", ""))

    for m in history_sorted:
        profit = float(m.get("profit", 0))
        stake = float(m.get("stake", 0))
        is_finance = m.get("sport") == "FINANCE"

        # 1. Zawsze aktualizujemy offset dla Bankrolla i Wykresu
        current_balance_offset += profit
        graph_data.append(round(base_capital + current_balance_offset, 2))

        # 2. Statystyki czysto bukmacherskie liczymy TYLKO dla meczów
        if not is_finance:
            betting_profit_total += profit
            total_staked += stake
            
            t = m.get("time")
            if t:
                try:
                    mt = datetime.fromisoformat(t.replace("Z", "+00:00"))
                    if now - mt < timedelta(hours=24):
                        profit_24h += profit
                except:
                    pass

    bankroll = base_capital + current_balance_offset
    yield_val = (betting_profit_total / total_staked * 100) if total_staked > 0 else 0

    stats = {
        "bankroll": round(bankroll, 2),
        "zysk_total": round(betting_profit_total, 2),
        "zysk_24h": round(profit_24h, 2),
        "obrot": round(total_staked, 2),
        "yield": round(yield_val, 2),
        "last_sync": now.strftime("%d.%m.%Y %H:%M"),
        "upcoming_val": remaining_count,
        "history_graph": graph_data[-100:]
    }

    with open(STATS_JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=4)

    # Celność: Tylko dla obiektów niebędących wypłatami
    matches_only = [m for m in history if m.get("sport") != "FINANCE"]
    wins = sum(1 for m in matches_only if m.get("status") == "WIN")
    total = sum(1 for m in matches_only if m.get("status") in ["WIN", "LOSS"])
    accuracy = (wins / total * 100) if total > 0 else 0

    msg = [
        "📊 <b>DASHBOARD UPDATED</b>",
        f"🏦 Bankroll: <b>{round(bankroll,2)} PLN</b>",
        f"💰 Zysk Total: {round(betting_profit_total,2)} PLN",
        f"📅 Ostatnie 24h: {round(profit_24h,2)} PLN",
        f"📈 Yield: {round(yield_val,2)}% | Celność: {round(accuracy,1)}%",
        "━━━━━━━━━━━━━━━",
        "📝 <b>OSTATNIE:</b>"
    ]

    for m in reversed(history[-5:]):
        if m.get("sport") == "FINANCE":
            icon = "🏦"
            label = "WYPŁATA ŚRODKÓW"
        else:
            icon = "✅" if m.get("status") == "WIN" else "❌" if m.get("status") == "LOSS" else "⚪"
            label = f"{m.get('home')} - {m.get('away')}"
            
        msg.append(f"{icon} {label} ({m.get('profit')} PLN)")

    send_telegram_results("\n".join(msg))

# ================= SETTLEMENT =================
def settle_matches():
    api_keys = get_all_api_keys()
    if not api_keys or not os.path.exists(COUPONS_FILE):
        return

    with open(COUPONS_FILE, "r", encoding="utf-8") as f:
        active_coupons = json.load(f)

    if not active_coupons:
        # Nawet jeśli nie ma kuponów, generujemy raport, by odświeżyć staty/wykres
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
            history = []

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
            home = match.get("home_team")
            away = match.get("away_team")
            hs = scores.get(home, 0)
            as_ = scores.get(away, 0)

            status = "LOSS"
            profit = -float(c.get("stake", 0))

            if hs == as_:
                status = "VOID"
                profit = 0.0
            else:
                if c.get("outcome") == home and hs > as_:
                    status = "WIN"
                elif c.get("outcome") == away and as_ > hs:
                    status = "WIN"

                if status == "WIN":
                    stake = float(c.get("stake", 0))
                    odds = float(c.get("odds", 0))
                    profit = round(stake * odds - stake, 2)

            history.append({
                **c,
                "profit": round(profit, 2),
                "status": status,
                "score": f"{hs}:{as_}"
            })
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
