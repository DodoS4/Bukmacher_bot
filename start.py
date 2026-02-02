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
MAX_TIPS_PER_LEAGUE = 3

# ================= POMOCNICZE =================
def get_secret(name):
    val = os.environ.get(name)
    return str(val).strip() if val else None

def send_telegram(message, mode="HTML"):
    token = get_secret("T_TOKEN")
    chat = get_secret("T_CHAT")
    if not token or not chat:
        print("⚠️ BRAK T_TOKEN lub T_CHAT – Telegram nie działa!")
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat, "text": message, "parse_mode": mode},
            timeout=15
        )
    except Exception as e:
        print("Błąd Telegram:", e)

def get_all_keys():
    keys = []
    for i in range(1, 11):
        name = "ODDS_KEY" if i == 1 else f"ODDS_KEY_{i}"
        val = get_secret(name)
        if val:
            keys.append(val)
    return keys

def safe_read_index():
    if os.path.exists(KEY_STATE_FILE):
        try:
            return int(open(KEY_STATE_FILE).read().strip())
        except:
            return 0
    return 0

def save_index(idx):
    open(KEY_STATE_FILE, "w").write(str(idx))

# ===== FILTR KURSÓW (DZIAŁAJĄCY) =====
def odd_allowed(sport, market, odd):
    # upraszczamy – łapiemy wszystko w sensownym przedziale
    return 1.6 <= odd <= 4.5

# ================= MAIN =================
def main():
    print(f"\n🚀 --- START BOT PRO: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")

    api_keys = get_all_keys()
    if not api_keys:
        print("❌ Brak kluczy API!")
        return

    idx = safe_read_index() % len(api_keys)

    coupons = json.load(open(COUPONS_FILE)) if os.path.exists(COUPONS_FILE) else []
    sent_keys = {(c["id"], c.get("market"), c["outcome"]) for c in coupons}

    now = datetime.now(timezone.utc)
    max_future = now + timedelta(hours=96)   # 4 dni zamiast 48h

    scanned = 0
    new_tips = 0
    total_stake = 0

    for league, label in SPORTS_CONFIG.items():
        print(f"🔍 Skanowanie: {label}")
        scanned += 1
        league_tips = 0

        data = None
        for _ in range(len(api_keys)):
            try:
                r = requests.get(
                    f"https://api.the-odds-api.com/v4/sports/{league}/odds/",
                    params={
                        "apiKey": api_keys[idx],
                        "regions": "eu",
                        "markets": "h2h,totals,btts,spreads"
                    },
                    timeout=15
                )

                if r.status_code == 200:
                    data = r.json()
                    break
                idx = (idx + 1) % len(api_keys)

            except:
                idx = (idx + 1) % len(api_keys)

        if not data:
            print(f"⚠️ Brak danych dla {label}")
            continue

        candidates = 0

        for event in data:
            try:
                m_time = datetime.fromisoformat(event["commence_time"].replace("Z", "+00:00"))
                if not (now < m_time < max_future):
                    continue
            except:
                continue

            for b in event.get("bookmakers", []):
                for m in b.get("markets", []):
                    market_key = m["key"]

                    for o in m.get("outcomes", []):
                        key = (event["id"], market_key, o["name"])

                        if key in sent_keys:
                            continue

                        if not odd_allowed(league, market_key, o["price"]):
                            continue

                        if league_tips >= MAX_TIPS_PER_LEAGUE:
                            break

                        candidates += 1
                        new_tips += 1
                        stake = BASE_STAKE
                        total_stake += stake

                        msg = (
                            f"<b>{label}</b>\n"
                            f"🏒 {event['home_team']} vs {event['away_team']}\n"
                            f"📊 Rynek: {market_key}\n"
                            f"✅ Typ: <b>{o['name']}</b>\n"
                            f"📈 Kurs: <b>{o['price']}</b>\n"
                            f"💰 Stawka: <b>{stake} PLN</b>"
                        )

                        send_telegram(msg)

                        coupons.append({
                            "id": event["id"],
                            "home": event["home_team"],
                            "away": event["away_team"],
                            "market": market_key,
                            "outcome": o["name"],
                            "odds": o["price"],
                            "stake": stake,
                            "sport": league,
                            "time": event["commence_time"]
                        })

                        sent_keys.add(key)
                        league_tips += 1
                        break

        print(f"📊 {label} | Kandydaci: {candidates}")

    print("\n📤 PODSUMOWANIE")
    print(f"📊 Ligi: {scanned}")
    print(f"🎯 Nowe typy: {new_tips}")
    print(f"💰 Łączna stawka: {total_stake} PLN")
    print(f"📄 Kupony zapisane: {len(coupons)}")

    json.dump(coupons, open(COUPONS_FILE, "w", encoding="utf-8"), indent=4)
    save_index(idx)

if __name__ == "__main__":
    main()