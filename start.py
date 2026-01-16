import requests
import json
import os
from datetime import datetime, timedelta, timezone
from dateutil import tz

# ================= KONFIGURACJA =================
# Pobieranie wszystkich dostępnych kluczy (ODDS_KEY oraz ODDS_KEY_1 do ODDS_KEY_5)
API_KEYS = [os.getenv(f"ODDS_KEY_{i}") for i in range(1, 6) if os.getenv(f"ODDS_KEY_{i}")]
if not API_KEYS:
    main_key = os.getenv("ODDS_KEY")
    if main_key:
        API_KEYS = [main_key]

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
        print("[ERROR] Brak T_TOKEN lub T_CHAT!")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        resp = requests.post(url, json={
            "chat_id": chat, 
            "text": message, 
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        })
    except Exception as e:
        print(f"[ERROR] Błąd wysyłki Telegram: {e}")

def get_matches_with_rotation(sport):
    """Pobiera mecze, rotując kluczami w razie błędu 429 (limit)"""
    url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
    params = {
        'regions': 'eu',
        'markets': 'h2h',
        'oddsFormat': 'decimal'
    }

    for key in API_KEYS:
        params['apiKey'] = key
        try:
            resp = requests.get(url, params=params, timeout=15)
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 429:
                print(f"[INFO] Klucz {key[:5]}... wyczerpany. Próbuję kolejny.")
                continue
            else:
                print(f"[WARN] API Error {resp.status_code} dla {sport}")
        except Exception as e:
            print(f"[ERROR] Błąd połączenia: {e}")
    return []

def main():
    now = datetime.now(timezone.utc)
    max_time = now + timedelta(hours=MAX_HOURS_AHEAD)

    # Wczytaj istniejące mecze, by uniknąć duplikatów i zachować stare rekordy
    all_matches_dict = {}
    if os.path.exists(COUPON_FILE):
        try:
            with open(COUPON_FILE, "r", encoding="utf-8") as f:
                old_data = json.load(f)
                # Tworzymy słownik ID: mecz
                all_matches_dict = {m["id"]: m for m in old_data if "id" in m}
        except:
            all_matches_dict = {}

    new_found_count = 0

    for sport, icon in SPORTS_CONFIG.items():
        print(f"Skanuję {sport}...")
        matches = get_matches_with_rotation(sport)

        for m in matches:
            try:
                match_id = m["id"]
                utc_time = datetime.fromisoformat(m["commence_time"].replace("Z", "+00:00"))
                
                # Filtry czasu i dostępności bukmacherów
                if not (now <= utc_time <= max_time): continue
                if not m.get("bookmakers"): continue

                # Polski czas do powiadomienia
                pl_zone = tz.gettz('Europe/Warsaw')
                date_str = utc_time.astimezone(pl_zone).strftime("%d.%m | %H:%M")

                # Sprawdzamy kursy u pierwszego dostępnego bukmachera
                outcomes = m["bookmakers"][0]["markets"][0]["outcomes"]
                for outcome in outcomes:
                    odds = outcome["price"]
                    
                    if MIN_ODDS <= odds <= MAX_ODDS:
                        # Jeśli meczu nie było jeszcze w bazie, wyślij powiadomienie
                        if match_id not in all_matches_dict:
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
                            new_found_count += 1

                        # Aktualizujemy/Dodajemy do słownika
                        all_matches_dict[match_id] = {
                            "id": match_id,
                            "sport_key": sport,
                            "sport": m["sport_title"],
                            "home": m["home_team"],
                            "away": m["away_team"],
                            "time": m["commence_time"],
                            "odds": odds,
                            "pick": outcome["name"]
                        }
                        break # Bierzemy tylko pierwszy pasujący typ z meczu
            except Exception as e:
                print(f"[WARN] Błąd meczu {m.get('id')}: {e}")

    # Usuwamy mecze, które już się odbyły (sprzątanie bazy)
    current_matches = [
        m for m in all_matches_dict.values() 
        if datetime.fromisoformat(m["time"].replace("Z", "+00:00")) > now - timedelta(hours=6)
    ]

    # Zapis do pliku
    with open(COUPON_FILE, "w", encoding="utf-8") as f:
        json.dump(current_matches, f, indent=4, ensure_ascii=False)
    
    print(f"[SUCCESS] Nowych: {new_found_count}. W bazie: {len(current_matches)}.")

if __name__ == "__main__":
    main()
