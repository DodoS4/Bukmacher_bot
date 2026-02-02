import os
import requests
import json
from datetime import datetime, timedelta, timezone

# ================= KONFIGURACJA LIG (RĘCZNA) =================
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

# ================= PLIKI =================
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

def get_all_keys():
    keys = []
    for i in range(1, 11):
        name = "ODDS_KEY" if i == 1 else f"ODDS_KEY_{i}"
        val = get_secret(name)
        if val:
            keys.append(val)
    return keys

# ================= STAKE + VALUE =================
def get_smart_stake(league_key):
    multiplier = 1.0
    threshold = 1.035
    league_profit = 0

    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
            league_profit = sum(
                m.get("profit", 0)
                for m in history
                if m.get("sport") == league_key
            )
        except:
            pass

    if league_profit <= -700:
        multiplier, threshold = 0.5, 1.08
    elif league_profit >= 3000:
        multiplier = 1.6
    elif league_profit >= 1000:
        multiplier = 1.3

    stake = BASE_STAKE * multiplier

    if "icehockey" in league_key:
        threshold -= 0.01
        if league_profit > 0:
            stake *= 1.25

    return round(stake, 2), round(threshold, 3)

# ================= MAIN =================
def main():
    print(f"🚀 START BOT PRO: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    api_keys = get_all_keys()
    if not api_keys:
        print("❌ Brak kluczy API")
        return

    try:
        with open(KEY_STATE_FILE, "r") as f:
            idx = int(f.read().strip()) % len(api_keys)
    except:
        idx = 0

    all_coupons = []
    if os.path.exists(COUPONS_FILE):
        try:
            with open(COUPONS_FILE, "r", encoding="utf-8") as f:
                all_coupons = json.load(f)
        except:
            pass

    already_sent = {c["id"] for c in all_coupons}
    now = datetime.now(timezone.utc)
    max_future = now + timedelta(hours=48)
    new_bets = 0

    for league, emoji in SPORTS_CONFIG.items():
        print(f"\n🔍 {emoji} {league.upper()}")
        stake, threshold = get_smart_stake(league)
        data = None

        for _ in range(len(api_keys)):
            url = f"https://api.the-odds-api.com/v4/sports/{league}/odds/"
            params = {
                "apiKey": api_keys[idx],
                "regions": "eu",
                "markets": "h2h"
            }

            try:
                print(f"  📡 Klucz #{idx+1}...", end=" ")
                r = requests.get(url, params=params, timeout=15)

                if r.status_code == 200:
                    data = r.json()
                    print("OK")
                    break
                elif r.status_code == 429:
                    print("LIMIT")
                    idx = (idx + 1) % len(api_keys)
                elif r.status_code == 404:
                    print("BRAK LIGI")
                    break
                else:
                    print(f"Błąd {r.status_code}")
                    break
            except:
                print("TIMEOUT")
                idx = (idx + 1) % len(api_keys)

        if not data:
            continue

        print(f"  📈 Mecze: {len(data)}")

        for event in data:
            if event["id"] in already_sent:
                continue

            try:
                m_time = datetime.fromisoformat(event["commence_time"].replace("Z", "+00:00"))
                if not (now < m_time < max_future):
                    continue
                display_time = m_time.astimezone(timezone(timedelta(hours=1)))
            except:
                continue

            prices = {}
            for b in event.get("bookmakers", []):
                for m in b.get("markets", []):
                    if m["key"] == "h2h":
                        for o in m["outcomes"]:
                            prices.setdefault(o["name"], []).append(o["price"])

            best_name = None
            best_val = 0
            best_odd = 0

            for name, plist in prices.items():
                if name.lower() == "draw":
                    continue

                max_p = max(plist)
                avg_p = sum(plist) / len(plist)
                val = max_p / avg_p

                req = threshold + (0.02 if max_p >= 2.5 else 0)

                if 1.8 <= max_p <= 4.5 and val > req and val > best_val:
                    best_name = name
                    best_val = val
                    best_odd = max_p

            if best_name:
                msg = (
                    f"{emoji} <b>{league.upper()}</b>\n"
                    f"━━━━━━━━━━━━━━━\n"
                    f"🏟 {event['home_team']} vs {event['away_team']}\n"
                    f"⏰ {display_time.strftime('%d.%m | %H:%M')}\n\n"
                    f"✅ Typ: <b>{best_name}</b>\n"
                    f"📈 Kurs: <b>{best_odd}</b>\n"
                    f"💰 Stawka: <b>{stake} PLN</b>\n"
                    f"📊 Value: <b>+{round((best_val-1)*100,1)}%</b>"
                )

                send_telegram(msg)

                all_coupons.append({
                    "id": event["id"],
                    "home": event["home_team"],
                    "away": event["away_team"],
                    "outcome": best_name,
                    "odds": best_odd,
                    "stake": stake,
                    "sport": league,
                    "time": event["commence_time"]
                })

                already_sent.add(event["id"])
                new_bets += 1

    with open(KEY_STATE_FILE, "w") as f:
        f.write(str(idx))

    with open(COUPONS_FILE, "w", encoding="utf-8") as f:
        json.dump(all_coupons, f, indent=4)

    print(f"\n✅ KONIEC | Nowe typy: {new_bets}")
    print(f"📊 Aktywne kupony: {len(all_coupons)}")

if __name__ == "__main__":
    main()
