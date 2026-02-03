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
BASE_STAKE = 250

# ================= POMOCNICZE =================
def get_secret(name):
    val = os.environ.get(name)
    return str(val).strip() if val else None

def send_telegram(message, mode="HTML"):
    token = get_secret("T_TOKEN")
    chat = get_secret("T_CHAT")
    if not token or not chat:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat, "text": message, "parse_mode": mode},
            timeout=15
        )
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
    threshold = 1.035
    profit = 0

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

# ===== FILTR KURSÓW (BEZ ASIAN) =====
def odd_allowed(sport, market, odd):
    if "icehockey" in sport:
        if market == "totals":
            return 1.45 <= odd <= 2.30
        if market == "h2h":
            return 1.8 <= odd <= 4.6
    if "soccer" in sport:
        if market in ["totals", "btts"]:
            return 1.65 <= odd <= 3.5
        if market == "h2h":
            return 1.9 <= odd <= 4.4
    return False

# ================= MAIN =================
def main():
    print(f"\n🚀 --- START BOT PRO: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")

    api_keys = get_all_keys()
    if not api_keys:
        print("❌ Brak kluczy API")
        return

    idx = int(open(KEY_STATE_FILE).read().strip()) if os.path.exists(KEY_STATE_FILE) else 0
    idx %= len(api_keys)

    coupons = json.load(open(COUPONS_FILE)) if os.path.exists(COUPONS_FILE) else []
    sent_ids = {c["id"] for c in coupons}

    now = datetime.now(timezone.utc)
    max_future = now + timedelta(hours=48)

    scanned = 0
    new_tips = 0
    total_stake = 0

    for league, label in SPORTS_CONFIG.items():
        print(f"🔍 Skanowanie: {label}")
        stake, threshold = get_smart_stake(league)

        scanned += 1
        data = None

        for _ in range(len(api_keys)):
            try:
                r = requests.get(
                    f"https://api.the-odds-api.com/v4/sports/{league}/odds/",
                    params={"apiKey": api_keys[idx], "regions": "eu", "markets": "h2h,totals,btts"},
                    timeout=15
                )
                if r.status_code == 200:
                    data = r.json()
                    break
                idx = (idx + 1) % len(api_keys)
            except:
                idx = (idx + 1) % len(api_keys)

        candidates = 0

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

            for b in event.get("bookmakers", []):
                for m in b.get("markets", []):
                    for o in m.get("outcomes", []):
                        if not odd_allowed(league, m["key"], o["price"]):
                            continue

                        candidates += 1
                        new_tips += 1
                        total_stake += stake

                        send_telegram(
                            f"<b>{label}</b>\n"
                            f"🏒 {event['home_team']} vs {event['away_team']}\n"
                            f"✅ Typ: <b>{o['name']}</b>\n"
                            f"📈 Kurs: <b>{o['price']}</b>\n"
                            f"💰 Stawka: <b>{stake} PLN</b>"
                        )

                        coupons.append({
                            "id": event["id"],
                            "home": event["home_team"],
                            "away": event["away_team"],
                            "outcome": o["name"],
                            "odds": o["price"],
                            "stake": stake,
                            "sport": league,
                            "time": event["commence_time"]
                        })

                        sent_ids.add(event["id"])
                        break

        print(f"📊 {label} | ✅ kandydaci: {candidates}\n")

    print("📤 WYSYŁANIE TYPÓW")
    print("━━━━━━━━━━━━━━━━")
    print(f"📊 Ligi przeskanowane: {scanned}")
    print(f"🎯 Nowe typy: {new_tips}")
    print(f"💰 Łączna stawka: {total_stake} PLN")
    print(f"📊 Aktywne kupony: {len(coupons)}\n")

    # ===== DEBUG ROZLICZEŃ =====
    if os.path.exists(HISTORY_FILE):
        print("📊 ROZLICZONE MECZE (ostatnie)\n")
        history = json.load(open(HISTORY_FILE, "r", encoding="utf-8"))
        for h in history[-5:]:
            if h.get("status") in ["WIN", "LOSS"]:
                emoji = "✅🔥" if h["profit"] > 0 else "❌"
                print(f"{h['home']} vs {h['away']} — {h['outcome']} {emoji}")
                print(f"💰 {h['profit']} PLN\n")

    json.dump(coupons, open(COUPONS_FILE, "w", encoding="utf-8"), indent=4)
    open(KEY_STATE_FILE, "w").write(str(idx))


if __name__ == "__main__":
    main()
