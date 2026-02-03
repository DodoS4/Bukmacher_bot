import os
import requests
import json
from datetime import datetime, timedelta, timezone

# ================= KONFIGURACJA LIG =================
SPORTS_CONFIG = {
    "icehockey_nhl": "🏒 NHL",
    "icehockey_sweden_hockeyallsvenskan": "🇸🇪 HockeyAllsvenskan",
    "icehockey_finland_liiga": "🇫🇮 Liiga",
    "icehockey_germany_del": "🇩🇪 DEL",
    "icehockey_czech_extraliga": "🇨🇿 Extraliga",
    "icehockey_switzerland_nla": "🇨🇭 NLA",
    "icehockey_austria_liga": "🇦🇹 ICEHL",
    "icehockey_denmark_metal_ligaen": "🇩🇰 Metal Ligaen",
    "icehockey_norway_eliteserien": "🇳🇴 Eliteserien",
    "icehockey_slovakia_extraliga": "🇸🇰 Extraliga",
    "soccer_epl": "🏴 Premier League",
    "soccer_germany_bundesliga": "🇩🇪 Bundesliga",
    "soccer_italy_serie_a": "🇮🇹 Serie A",
    "soccer_spain_la_liga": "🇪🇸 La Liga",
    "soccer_poland_ekstraklasa": "🇵🇱 Ekstraklasa",
    "soccer_france_ligue_one": "🇫🇷 Ligue 1",
    "soccer_portugal_primeira_liga": "🇵🇹 Primeira Liga",
    "soccer_netherlands_eredivisie": "🇳🇱 Eredivisie",
    "soccer_austria_bundesliga": "🇦🇹 Bundesliga",
    "soccer_denmark_superliga": "🇩🇰 Superliga",
    "soccer_greece_super_league": "🇬🇷 Super League",
    "soccer_switzerland_superleague": "🇨🇭 Super League",
}

HISTORY_FILE = "history.json"
COUPONS_FILE = "coupons.json"
KEY_STATE_FILE = "key_index.txt"
BASE_STAKE = 20

# ================= LICZNIKI DEBUG =================
sent_count = 0
sent_stake_sum = 0.0
sent_potential_return = 0.0
scanned_leagues = 0

# ================= POMOCNICZE =================
def get_secret(name):
    val = os.environ.get(name)
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

def get_smart_stake(league_key):
    multiplier = 1.0
    threshold = 1.025  # 🔥 LUŹNIEJSZY THRESHOLD
    profit = 0

    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
            profit = sum(
                m.get("profit", 0)
                for m in history
                if m.get("sport") == league_key and m.get("status") != "ARCHIVED"
            )

            if profit <= -300:
                multiplier, threshold = 0.5, 1.08
            elif profit >= 1000:
                multiplier = 1.5
            elif profit >= 500:
                multiplier = 1.2
        except:
            pass

    stake = BASE_STAKE * multiplier
    if "icehockey" in league_key:
        threshold -= 0.01
        if profit > 0:
            stake *= 1.2

    return round(stake, 2), round(threshold, 3)

# ================= MAIN =================
def main():
    global sent_count, sent_stake_sum, sent_potential_return, scanned_leagues

    print(f"\n🚀 --- START BOT PRO (H2H + TOTALS): {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")

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
    max_future = now + timedelta(hours=72)  # 🔥 więcej meczów

    for league, label in SPORTS_CONFIG.items():
        scanned_leagues += 1
        print(f"\n🔍 Skanowanie: {label}")

        stake, threshold = get_smart_stake(league)
        data = None

        for _ in range(len(api_keys)):
            url = f"https://api.the-odds-api.com/v4/sports/{league}/odds/"
            params = {
                "apiKey": api_keys[idx],
                "regions": "eu",
                "markets": "h2h,totals",
                "oddsFormat": "decimal"
            }
            try:
                r = requests.get(url, params=params, timeout=15)
                if r.status_code == 200:
                    data = r.json()
                    break
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
            except:
                continue

            best_bet = None
            best_val = 0

            for b in event.get("bookmakers", []):
                for m in b.get("markets", []):
                    # H2H
                    if m["key"] == "h2h":
                        for o in m["outcomes"]:
                            if o["name"].lower() == "draw":
                                continue
                            price = o["price"]
                            val = price / 1.95
                            if 1.75 <= price <= 4.2 and val > threshold and val > best_val:
                                best_val = val
                                best_bet = (o["name"], price)

                    # TOTALS
                    if m["key"] == "totals":
                        for o in m["outcomes"]:
                            price = o["price"]
                            name = f"{o['name']} {o.get('point')}"
                            val = price / 1.92
                            if 1.65 <= price <= 2.6 and val > threshold and val > best_val:
                                best_val = val
                                best_bet = (name, price)

            if best_bet:
                name, odd = best_bet
                msg = (
                    f"<b>{label}</b>\n"
                    f"🏟 {event['home_team']} vs {event['away_team']}\n"
                    f"⏰ {m_time.astimezone(timezone(timedelta(hours=1))).strftime('%d.%m %H:%M')}\n\n"
                    f"✅ Typ: <b>{name}</b>\n"
                    f"📈 Kurs: <b>{odd}</b>\n"
                    f"💰 Stawka: <b>{stake} PLN</b>\n"
                    f"📊 Value: <b>+{round((best_val-1)*100,1)}%</b>"
                )

                send_telegram(msg)

                coupons.append({
                    "id": event["id"],
                    "home": event["home_team"],
                    "away": event["away_team"],
                    "outcome": name,
                    "odds": odd,
                    "stake": stake,
                    "sport": league,
                    "time": event["commence_time"]
                })

                sent_ids.add(event["id"])
                sent_count += 1
                sent_stake_sum += stake
                sent_potential_return += stake * odd

    with open(KEY_STATE_FILE, "w") as f:
        f.write(str(idx))

    with open(COUPONS_FILE, "w", encoding="utf-8") as f:
        json.dump(coupons, f, indent=4)

    print("\n📤 PODSUMOWANIE")
    print("━━━━━━━━━━━━━━")
    print(f"📊 Ligi przeskanowane: {scanned_leagues}")
    print(f"🎯 Nowe typy: {sent_count}")
    print(f"💰 Stawka łącznie: {round(sent_stake_sum,2)} PLN")
    print(f"📈 Potencjalny zwrot: {round(sent_potential_return,2)} PLN")
    print(f"📊 Aktywne kupony: {len(coupons)}")

if __name__ == "__main__":
    main()
