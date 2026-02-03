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
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat, "text": message, "parse_mode": "HTML"},
            timeout=15
        )
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
        try:
            r = requests.get(
                f"https://api.the-odds-api.com/v4/sports/{sport}/scores/",
                params={"apiKey": key, "daysFrom": 5},
                timeout=15
            )
            if r.status_code == 200:
                return r.json()
        except:
            continue
    return None

# ================= DASHBOARD =================
def generate_report(history, remaining_count):
    now = datetime.now(timezone.utc)
    base_capital = 5000.0

    total_profit = 0.0
    total_staked = 0.0
    profit_24h = 0.0
    graph_data = [base_capital]

    history_sorted = sorted(history, key=lambda x: x.get("time", ""))

    for m in history_sorted:
        profit = float(m.get("profit", 0))
        stake = float(m.get("stake", 0))

        total_profit += profit
        total_staked += stake
        graph_data.append(round(base_capital + total_profit, 2))

        try:
            mt = datetime.fromisoformat(m["time"].replace("Z", "+00:00"))
            if now - mt < timedelta(hours=24):
                profit_24h += profit
        except:
            pass

    bankroll = base_capital + total_profit
    yield_val = (total_profit / total_staked * 100) if total_staked > 0 else 0

    stats = {
        "bankroll": round(bankroll, 2),
        "zysk_total": round(total_profit, 2),
        "zysk_24h": round(profit_24h, 2),
        "obrot": round(total_staked, 2),
        "yield": round(yield_val, 2),
        "last_sync": now.strftime("%d.%m.%Y %H:%M"),
        "upcoming_val": remaining_count,
        "history_graph": graph_data[-100:]
    }

    with open(STATS_JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=4)

    wins = sum(1 for m in history if m.get("status") == "WIN")
    total = sum(1 for m in history if m.get("status") in ["WIN", "LOSS"])
    accuracy = (wins / total * 100) if total > 0 else 0
