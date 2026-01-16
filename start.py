import requests
import json
import os
from datetime import datetime, timedelta, timezone

# ================= KONFIGURACJA =================
# Pobieranie kluczy z GitHub Secrets
API_KEYS = [os.getenv(f"ODDS_KEY_{i}") for i in range(1, 6) if os.getenv(f"ODDS_KEY_{i}")]
if not API_KEYS:
    API_KEYS = [os.getenv("ODDS_KEY")]

# POPRAWIONE NAZWY LIG (zgodnie z dokumentacją API)
SPORTS = [
    "basketball_nba", 
    "icehockey_nhl",     # Zmieniono z hockey_nhl na icehockey_nhl
    "soccer_epl", 
    "soccer_spain_la_liga"
]

COUPON_FILE = "coupons.json"

# FILTRY KURSÓW
MIN_ODDS = 1.50
MAX_ODDS = 2.50
MAX_HOURS_AHEAD = 48 

def send_telegram(message):
    token = os.getenv("T_TOKEN")
    chat = os.getenv("T_CHAT")
    if not token or not chat: return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        requests.post(url, json={"chat_id": chat, "text": message, "parse_mode": "HTML"})
    except:
        pass

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
        print(f"[DEBUG] API Status dla {sport}: {resp.status_code}")
        return []
    except Exception as e:
        print(f"[ERROR] {sport}: {e}")
        return []

def main():
    all_filtered_matches = []
    now = datetime.now(timezone.utc)
    max_time = now + timedelta(hours=MAX_HOURS_AHEAD)

    # Wczytaj stare mecze, żeby nie dublować powiadomień na Telegramie
    existing_ids = []
    if os.path.exists(COUPON_FILE):
        try:
            with open(COUPON_FILE, "r") as f:
                old_data = json.load(f)
                existing_ids = [m["id"] for m in old_data if "id" in m]
        except:
            existing_ids = []

    for sport in SPORTS:
        print(f"Sprawdzam: {sport}...")
        matches = []
        for key in API_KEYS:
            if not key: continue
            matches = get_matches(sport, key)
            if matches: break 

        for m in matches:
            try:
                # NAPRAWIONE KLUCZE: home_team i away_team
                m_time = datetime.fromisoformat(m["commence_time"].replace("Z", "+00:00"))
                
                if not (now <= m_time <= max_time):
                    continue

                if not m.get("bookmakers"):
                    continue

                # Wybieramy kursy (zazwyczaj od pierwszego bukmachera na liście)
                outcomes = m["bookmakers"][0]["markets"][0]["outcomes"]
                
                for outcome in outcomes:
                    odds = outcome["price"]
                    if MIN_ODDS <= odds <= MAX_ODDS:
                        match_id = m["id"]
                        
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

                        # Wyślij na Telegram tylko jeśli to NOWY mecz (nie ma go w starym coupons.json)
                        if match_id not in existing_ids:
                            msg = (f"🏀 <b>{m['sport_title']}</b>\n"
                                   f"{m['home_team']} vs {m['away_team']}\n"
                                   f"🎯 Typ: <b>{outcome['name']}</b>\n"
                                   f"📈 Kurs: <b>{odds}</b>")
                            send_telegram(msg)
                        break 
            except Exception as e:
                print(f"[WARN] Błąd przetwarzania meczu: {e}")

    # Zapisz wszystko do pliku (lista, nie słownik {})
    with open(COUPON_FILE, "w", encoding="utf-8") as f:
        json.dump(all_filtered_matches, f, indent=4, ensure_ascii=False)
    
    print(f"[SUCCESS] Zapisano {len(all_filtered_matches)} ofert.")

if __name__ == "__main__":
    main()
