import requests
import os
from datetime import datetime, timedelta, timezone
import json

# ================= KONFIGURACJA =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")
API_KEYS = [
    os.getenv("ODDS_KEY"),
    os.getenv("ODDS_KEY_2"),
    os.getenv("ODDS_KEY_3"),
    os.getenv("ODDS_KEY_4"),
    os.getenv("ODDS_KEY_5"),
]

LEAGUES = ["NBA", "Euroleague", "Premier League", "La Liga", "NHL"]

COUPONS_FILE = "coupons.json"

# ================= FUNKCJE =================

def get_upcoming_matches(api_key):
    url = f"https://api.the-odds-api.com/v4/sports/upcoming/odds/?apiKey={api_key}"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        matches = resp.json()
        print(f"[DEBUG] Klucz {api_key} zwrócił {len(matches)} meczów")
        return matches
    except Exception as e:
        print(f"[ERROR] Problem z kluczem {api_key}: {e}")
        return []

def rotate_keys(keys):
    for key in keys:
        matches = get_upcoming_matches(key)
        if matches:
            return matches
    return []

def filter_matches(matches):
    now = datetime.now(timezone.utc)
    max_time = now + timedelta(hours=48)
    filtered = []
    for m in matches:
        try:
            match_dt = datetime.fromisoformat(m["commence_time"].replace("Z", "+00:00"))
            if match_dt >= now and match_dt <= max_time and m["league"] in LEAGUES:
                filtered.append(m)
        except Exception as e:
            print(f"[WARN] Niepoprawna data meczu: {m} -> {e}")
    print(f"[DEBUG] Po filtrze 48h i lig: {len(filtered)} meczów")
    return filtered

def prepare_coupons(matches):
    coupons = []
    for m in matches:
        home = m["home_team"]
        away = m["away_team"]
        league = m["league"]
        try:
            odds_home = m.get("odds_home") or m.get("odds_1")
            odds_away = m.get("odds_away") or m.get("odds_2")
            edge_home = m.get("edge_home", 0)
            edge_away = m.get("edge_away", 0)

            if edge_home > 5:
                pick = home
                edge = edge_home
                tag = "VALUE"
            elif edge_away > 5:
                pick = away
                edge = edge_away
                tag = "VALUE"
            else:
                if odds_home < odds_away:
                    pick = home
                    edge = edge_home
                else:
                    pick = away
                    edge = edge_away
                tag = "PEWNIAK"

            coupon = {
                "league": league,
                "home": home,
                "away": away,
                "pick": pick,
                "odds": odds_home if pick == home else odds_away,
                "edge": edge,
                "type": tag,
                "date": m["commence_time"],
                "status": "Pending"
            }
            coupons.append(coupon)
        except Exception as e:
            print(f"[WARN] Problem z tworzeniem kuponu: {m} -> {e}")
    print(f"[DEBUG] Przygotowano kupony: {len(coupons)}")
    return coupons

def send_to_telegram(coupons):
    for c in coupons:
        text = f"🏀 {c['league']}\n{c['home']} 🆚 {c['away']}\n🎯 Typ: {c['pick']} ({c['type']})\n💸 Kurs: {c['odds']} | ⏳ Pending\n📅 {c['date']}"
        url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
        try:
            resp = requests.post(url, data={"chat_id": T_CHAT, "text": text})
            if resp.status_code != 200:
                print(f"[ERROR] Telegram: {resp.text}")
        except Exception as e:
            print(f"[ERROR] Telegram exception: {e}")

def main():
    matches = rotate_keys(API_KEYS)
    if not matches:
        print("[INFO] Brak meczów do przetworzenia")
        return

    matches = filter_matches(matches)
    if not matches:
        print("[INFO] Brak meczów po filtrze 48h / ligi")
        return

    coupons = prepare_coupons(matches)

    print("[DEBUG] Przykładowe kupony:")
    for c in coupons[:3]:
        print(c)

    send_to_telegram(coupons)

    with open(COUPONS_FILE, "w", encoding="utf-8") as f:
        json.dump(coupons, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()