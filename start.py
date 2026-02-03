import os
import requests
import json
import time
from datetime import datetime, timedelta, timezone

# ================= KONFIGURACJA =================
SPORTS_CONFIG = {
    "soccer_epl": "🏴 Premier League",
    "soccer_germany_bundesliga": "🇩🇪 Bundesliga",
    "soccer_italy_serie_a": "🇮🇹 Serie A",
    "soccer_spain_la_liga": "🇪🇸 La Liga",
    "soccer_poland_ekstraklasa": "🇵🇱 Ekstraklasa",
    "icehockey_nhl": "🏒 NHL",
    "icehockey_sweden_hockeyallsvenskan": "🇸🇪 HockeyAllsvenskan",
}

HISTORY_FILE = "history.json"
COUPONS_FILE = "coupons.json"
KEY_STATE_FILE = "key_index.txt"

BASE_STAKE = 250
MAX_TIPS_PER_RUN = 8

# ================= POMOCNICZE =================
def get_secret(name):
    val = os.environ.get(name)
    return str(val).strip() if val else None


def send_telegram(message):
    token = get_secret("T_TOKEN")
    chat = get_secret("T_CHAT")
    if not token or not chat:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat, "text": message, "parse_mode": "HTML"},
            timeout=15
        )
        time.sleep(1.2)
    except Exception as e:
        print("⚠️ Telegram error:", e)


def get_all_keys():
    keys = []
    for i in range(1, 11):
        name = "ODDS_KEY" if i == 1 else f"ODDS_KEY_{i}"
        val = get_secret(name)
        if val:
            keys.append(val)
    return keys


# ================= LOGIKA RYNKÓW =================
def odd_allowed(sport, market, o):
    odd = o["price"]
    name = o["name"]

    # ========== ⚽ PIŁKA ==========
    if "soccer" in sport:

        # BTTS YES
        if market == "btts":
            if name.lower() != "yes":
                return False
            return 1.65 <= odd <= 3.20

        # Over 2.5 / 3.5
        if market == "totals":
            line = o.get("point")
            if line not in [2.5, 3.5]:
                return False
            return 1.55 <= odd <= 3.00

        # Double Chance X2
        if market == "double_chance":
            if name != "Draw/Away":
                return False
            return 1.40 <= odd <= 2.30

        # H2H underdog
        if market == "h2h":
            return odd > 2.20

    # ========== 🏒 HOKEJ ==========
    if "icehockey" in sport:

        # unikamy 3-way ML
        if market == "h2h" and name.lower() == "draw":
            return False

        # Over 4.5 / 5.5
        if market == "totals":
            line = o.get("point")
            if line not in [4.5, 5.5]:
                return False
            return 1.45 <= odd <= 2.30

        # H2H tylko faworyt
        if market == "h2h":
            return 1.50 <= odd <= 2.40

    return False


# ================= MAIN =================
def main():
    print(f"\n🚀 START BOT | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    api_keys = get_all_keys()
    if not api_keys:
        print("❌ Brak kluczy API")
        return

    idx = int(open(KEY_STATE_FILE).read()) if os.path.exists(KEY_STATE_FILE) else 0
    idx %= len(api_keys)

    coupons = json.load(open(COUPONS_FILE)) if os.path.exists(COUPONS_FILE) else []
    sent_ids = {c["bet_id"] for c in coupons}

    now = datetime.now(timezone.utc)
    max_future = now + timedelta(hours=48)

    tips_sent = 0

    for league, label in SPORTS_CONFIG.items():
        print(f"🔍 Liga: {label}")

        data = None
        for _ in range(len(api_keys)):
            try:
                r = requests.get(
                    f"https://api.the-odds-api.com/v4/sports/{league}/odds/",
                    params={
                        "apiKey": api_keys[idx],
                        "regions": "eu",
                        "markets": "h2h,totals,btts,double_chance"
                    },
                    timeout=15
                )
                open(KEY_STATE_FILE, "w").write(str(idx))
                if r.st
