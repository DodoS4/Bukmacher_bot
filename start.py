import requests
import json
import os
from datetime import datetime, timedelta, timezone
from dateutil import tz

# ================= KONFIGURACJA =================
# Pobieranie kluczy z GitHub Secrets
API_KEYS = [os.getenv(f"ODDS_KEY_{i}") for i in range(1, 6) if os.getenv(f"ODDS_KEY_{i}")]
if not API_KEYS:
    API_KEYS = [os.getenv("ODDS_KEY")]

# KONFIGURACJA LIG I EMOJI
SPORTS_CONFIG = {
    "basketball_nba": "🏀",
    "icehockey_nhl": "🏒",
    "soccer_epl": "⚽",
    "soccer_spain_la_liga": "🇪🇸",
    "soccer_germany_bundesliga": "🇩🇪",
    "soccer_italy_serie_a": "🇮🇹",
    "soccer_france_ligue_one": "🇫🇷"
}

COUPON_FILE = "coupons.json"
MIN_ODDS = 1.50
MAX_ODDS = 2.50
MAX_HOURS_AHEAD = 48 

def send_telegram(message):
    token = os.getenv("T_TOKEN")
    chat = os.getenv("T_CHAT")
    if not token or not chat: 
        print("[ERROR] Brak T_TOKEN lub T_CHAT w Secrets!")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        resp = requests.post(url, json={
            "chat_id": chat, 
            "text": message, 
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        })
        if resp.status_code != 200:
            print(f"[ERROR] Telegram API: {resp.text}")
    except Exception as e:
        print(f"[ERROR] Błąd wysyłki Telegram: {e}")

def get_matches(sport, key):
    url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
    params = {
        'apiKey': key,
        'regions': 'eu',
        'markets': 'h2h',
        'oddsFormat': 'decimal'
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        if resp.status_code == 200:
            return resp.json()
        return []
    except:
        return []

def main():
    all_filtered_matches = []
    now = datetime.now(timezone.utc)
    max_time = now + timedelta(hours=MAX_HOURS_AHEAD)

    # Wczytaj już wysłane mecze, by uniknąć spamu
    existing_ids = []
    if os.path.exists(COUPON_FILE):
        try:
            with open(COUPON_FILE, "r", encoding="utf-8") as f:
                old_data = json.load(f)
                existing_ids = [m["id"] for m in old_data if "id" in m]
        except:
            existing_ids = []

    for sport, icon in SPORTS_CONFIG.items():
        print(f"Skanuję {sport}...")
        matches = []
        for key in API_KEYS:
            matches = get_matches(sport, key)
            if matches: break 

        for m in matches:
            try:
                # Czas meczu i konwersja na strefę PL
                utc_time = datetime.fromisoformat(m["commence_time"].replace("Z", "+00:00"))
                
                if not (now <= utc_time <= max_time): continue
                if not m.get("bookmakers"): continue

                # Formatuje datę na polski czas
                pl_zone = tz.gettz('Europe/Warsaw')
                local_time = utc_time.astimezone(pl_zone)
                date_str = local_time.strftime("%d.%m | %H:%M")

                # Sprawdzamy kursy (pierwszy bukmacher)
                outcomes = m["bookmakers"][0]["markets"][0]["outcomes"]
                for outcome in outcomes:
                    odds = outcome["price"]
                    
                    if MIN_ODDS <= odds <= MAX_ODDS:
                        match_id = m["id"]
                        
                        # Budujemy obiekt do zapisu
                        match_obj = {
                            "id": match_id,
                            "sport_key": sport,
                            "sport": m["sport_title"],
                            "home": m["home_team"],
                            "away": m["away_team"],
                            "time": m["commence_time"],
                            "odds": odds,
                            "pick": outcome["name"]
                        }
                        all_filtered_matches.append(match_obj)

                        # Wysyłamy wiadomość tylko jeśli to nowość
                        if match_id not in existing_ids:
                            msg = (
                                f"{icon} <b>{m['sport_title'].upper()}</b>\n"
                                f"━━━━━━━━━━━━━━━\n"
                                f"🏟 <b>{m['home_team']}</b> vs <b>{m['away_team']}</b>\n"
                                f"⏰ Start: <code>{date_str}</code>\n\n"
                                f"✅ Typ: <b>{outcome['name']}</b>\n"
                                f"📈 Kurs: <b>{odds:.2f}</b>\n"
                                f"━━━━━━━━━━━━━━━"
                            )
                            send_telegram(msg)
                        break 
            except Exception as e:
                print(f"[WARN] Błąd meczu {m.get('id')}: {e}")

    # Zapis do pliku
    with open(COUPON_FILE, "w", encoding="utf-8") as f:
        json.dump(all_filtered_matches, f, indent=4, ensure_ascii=False)
    
    print(f"[SUCCESS] Zapisano {len(all_filtered_matches)} ofert.")

if __name__ == "__main__":
    main()
