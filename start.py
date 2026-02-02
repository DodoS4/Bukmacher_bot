import os
import requests
import json
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus

# ================= KONFIGURACJA LIG =================
SPORTS_CONFIG = {
    "icehockey_nhl": "🏒",
    "icehockey_sweden_hockeyallsvenskan": "🇸🇪",
    "icehockey_finland_liiga": "🇫🇮",
    "icehockey_germany_del": "🇩🇪",
    "icehockey_czech_extraliga": "🇨🇿",
    "icehockey_switzerland_nla": "🇨🇭",
    "icehockey_austria_liga": "🇦🇹",
    "icehockey_denmark_metal_ligaen": "🇩🇰",
    "icehockey_norway_eliteserien": "🇳🇴",
    "icehockey_slovakia_extraliga": "🇸🇰",

    "soccer_epl": "⚽",
    "soccer_germany_bundesliga": "🇩🇪",
    "soccer_italy_serie_a": "🇮🇹",
    "soccer_spain_la_liga": "🇪🇸",
    "soccer_poland_ekstraklasa": "🇵🇱",
    "soccer_france_ligue_one": "🇫🇷",
    "soccer_portugal_primeira_liga": "🇵🇹",
    "soccer_netherlands_eredivisie": "🇳🇱",
    "soccer_austria_bundesliga": "🇦🇹",
    "soccer_denmark_superliga": "🇩🇰",
    "soccer_greece_super_league": "🇬🇷",
    "soccer_switzerland_superleague": "🇨🇭",

    "basketball_euroleague": "🏀"
}

HISTORY_FILE = "history.json"
COUPONS_FILE = "coupons.json"
KEY_STATE_FILE = "key_index.txt"
BASE_STAKE = 250

# ================= POMOCNICZE =================
def get_secret(name):
    val = os.environ.get(name) or os.getenv(name)
    return str(val).strip() if val else None

def send_telegram(message, mode="HTML"):
    token = get_secret("T_TOKEN")
    chat = get_secret("T_CHAT")
    if not token or not chat:
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat, "text": message, "parse_mode": mode}
    try:
        requests.post(url, json=payload, timeout=15)
    except:
        pass

# ================= LINKI DO BUKMACHERÓW =================
def build_bookie_links(home_team, away_team, best_bookie=None):
    query = quote_plus(f"{home_team} {away_team}")

    bookies = {
        "STS": f"https://www.sts.pl/search?q={query}",
        "Fortuna": f"https://www.efortuna.pl/search?phrase={query}",
        "Betclic": f"https://www.betclic.pl/search?q={query}",
    }

    lines = []
    for name, url in bookies.items():
        label = f"⭐ {name}" if name == best_bookie else name
        lines.append(f"🔗 {label}: {url}")

    return "\n".join(lines)

# ================= STAWKA / VALUE =================
def get_smart_stake(league_key):
    multiplier, threshold, profit = 1.0, 1.035, 0

    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
            profit = sum(m.get("profit", 0) for m in history if m.get("sport") == league_key)

            if profit <= -700:
                multiplier, threshold = 0.5, 1.08
            elif profit >= 3000:
                multiplier = 1.6
            elif profit >= 1000:
                multiplier = 1.3
        except:
            pass

    stake = BASE_STAKE * multiplier
    if "icehockey" in league_key:
        threshold -= 0.01
        if profit > 0:
            stake *= 1.25

    return round(stake, 2), round(threshold, 3)

def get_all_keys():
    keys = []
    for i in range(1, 11):
        name = "ODDS_KEY" if i == 1 else f"ODDS_KEY_{i}"
        val = get_secret(name)
        if val:
            keys.append(val)
    return keys

# ================= MAIN =================
def main():
    print(f"🚀 START BOT: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    api_keys = get_all_keys()
    if not api_keys:
        print("❌ Brak kluczy API")
        return

    try:
        with open(KEY_STATE_FILE, "r") as f:
            idx = int(f.read().strip()) % len(api_keys)
    except:
        idx = 0

    coupons = []
    if os.path.exists(COUPONS_FILE):
        try:
            with open(COUPONS_FILE, "r", encoding="utf-8") as f:
                coupons = json.load(f)
        except:
            pass

    sent_ids = {c["id"] for c in coupons}
    now = datetime.now(timezone.utc)
    max_future = now + timedelta(hours=48)

    for league, flag in SPORTS_CONFIG.items():
        print(f"\n🔍 {flag} {league.upper()}")
        stake, threshold = get_smart_stake(league)
        data = None

        for _ in range(len(api_keys)):
            url = f"https://api.the-odds-api.com/v4/sports/{league}/odds/"
            params = {"apiKey": api_keys[idx], "regions": "eu", "markets": "h2h"}
            try:
                resp = requests.get(url, params=params, timeout=15)
                if resp.status_code == 200:
                    data = resp.json()
                    break
                else:
                    idx = (idx + 1) % len(api_keys)
            except:
                idx = (idx + 1) % len(api_keys)

        if not data:
            continue

        for event in data:
            if event["id"] in sent_ids:
                continue

            try:
                m_time = datetime.fromisoformat(event["commence_time"].replace("Z", "+00:00"))
                if not (now < m_time < max_future):
                    continue
                m_local = m_time.astimezone(timezone(timedelta(hours=1)))
            except:
                continue

            prices = {}
            bookies_map = {}

            for bookie in event.get("bookmakers", []):
                for market in bookie.get("markets", []):
                    if market["key"] == "h2h":
                        for out in market["outcomes"]:
                            prices.setdefault(out["name"], []).append(out["price"])
                            bookies_map.setdefault(out["name"], {})[out["price"]] = bookie["title"]

            best_name, best_odd, best_val, best_bookie = None, 0, 0, None

            for name, odds in prices.items():
                if name.lower() == "draw":
                    continue

                max_odd = max(odds)
                avg_odd = sum(odds) / len(odds)
                value = max_odd / avg_odd

                req = threshold + (0.02 if max_odd >= 2.5 else 0)

                if 1.8 <= max_odd <= 4.5 and value > req and value > best_val:
                    best_name = name
                    best_odd = max_odd
                    best_val = value
                    best_bookie = bookies_map[name][max_odd]

            if best_name:
                links = build_bookie_links(
                    event["home_team"],
                    event["away_team"],
                    best_bookie
                )

                msg = (
                    f"{flag} <b>{league.replace('_', ' ').upper()}</b>\n"
                    f"━━━━━━━━━━━━━━━\n"
                    f"🏟 <b>{event['home_team']}</b> vs <b>{event['away_team']}</b>\n"
                    f"⏰ {m_local.strftime('%d.%m | %H:%M')}\n\n"
                    f"✅ Typ: <b>{best_name}</b>\n"
                    f"📈 Kurs: <b>{best_odd}</b>\n"
                    f"🏦 Najlepszy: <b>{best_bookie}</b>\n"
                    f"💰 Stawka: <b>{stake} PLN</b>\n\n"
                    f"{links}"
                )

                send_telegram(msg)

                coupons.append({
                    "id": event["id"],
                    "home": event["home_team"],
                    "away": event["away_team"],
                    "outcome": best_name,
                    "odds": best_odd,
                    "stake": stake,
                    "sport": league,
                    "time": event["commence_time"],
                    "bookmaker": best_bookie,
                    "status": "pending"
                })

                sent_ids.add(event["id"])

    with open(KEY_STATE_FILE, "w") as f:
        f.write(str(idx))

    with open(COUPONS_FILE, "w", encoding="utf-8") as f:
        json.dump(coupons, f, indent=4)

    print("✅ KONIEC SKANU")

if __name__ == "__main__":
    main()
