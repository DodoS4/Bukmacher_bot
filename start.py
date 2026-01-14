import requests, json, os
from datetime import datetime, timezone

# ================= CONFIG =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")
API_KEYS = [os.getenv(f"ODDS_KEY{i}") for i in ["", "_2", "_3", "_4", "_5"]]
API_KEYS = [k for k in API_KEYS if k]
COUPONS_FILE = "coupons.json"
TAX_PL = 0.88  # Podatek 12%

# Wybrane ligi
LEAGUES = [
    "basketball_nba",
    "basketball_euroleague",
    "icehockey_nhl",
    "soccer_epl",
    "soccer_uefa_champs_league",
    "basketball_wnba",
    "soccer_serie_a",
    "soccer_laliga",
    "soccer_bundesliga",
    "soccer_ligue1",
    "icehockey_khl",
    "soccer_eredivisie",
    "basketball_aba_league",
    "soccer_primeira_liga",
    "soccer_saprliiga"
]

# ================= FUNCTIONS =================
def send_msg(txt):
    if not T_TOKEN or not T_CHAT: return
    try:
        requests.post(f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
                      json={"chat_id": T_CHAT, "text": txt, "parse_mode": "HTML"})
    except Exception as e:
        print(f"[ERROR] Telegram send failed: {e}")

def load_coupons():
    if not os.path.exists(COUPONS_FILE): return []
    try:
        with open(COUPONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERROR] Nie można wczytać pliku coupons: {e}")
        return []

def save_coupons(coupons):
    try:
        with open(COUPONS_FILE, "w", encoding="utf-8") as f:
            json.dump(coupons, f, indent=2)
    except Exception as e:
        print(f"[ERROR] Nie można zapisać pliku coupons: {e}")

def fetch_odds(league_key):
    for key in API_KEYS:
        print(f"[DEBUG] Pobieram dane dla ligi: {league_key} | Klucz: {key}")
        try:
            r = requests.get(f"https://api.the-odds-api.com/v4/sports/{league_key}/odds/",
                             params={"apiKey": key, "regions": "eu", "markets": "h2h", "oddsFormat": "decimal", "dateFormat": "iso"})
            print(f"[DEBUG] Status: {r.status_code}")
            if r.status_code == 200:
                data = r.json()
                print(f"[DEBUG] Mecze pobrane: {len(data)}")
                return data
            else:
                print(f"[DEBUG] Odpowiedź API: {r.text}")
        except Exception as e:
            print(f"[ERROR] Błąd pobierania: {e}")
    return []

def generate_coupons():
    coupons = load_coupons()
    new_coupons = 0

    for league in LEAGUES:
        matches = fetch_odds(league)
        for m in matches:
            try:
                # Wybór value bet / pewniaka (prosta logika, można rozszerzyć)
                home_odds = m["bookmakers"][0]["markets"][0]["outcomes"][0]["price"]
                away_odds = m["bookmakers"][0]["markets"][0]["outcomes"][1]["price"]
                pick = m["bookmakers"][0]["markets"][0]["outcomes"][0]["name"] if home_odds < away_odds else m["bookmakers"][0]["markets"][0]["outcomes"][1]["name"]
                odds = min(home_odds, away_odds)

                coupon = {
                    "home": m["home_team"],
                    "away": m["away_team"],
                    "pick": pick,
                    "odds": odds,
                    "stake": 100.0,  # możesz zmienić
                    "status": "PENDING",
                    "league": league,
                    "league_key": league,
                    "date": m["commence_time"],
                    "edge": round(abs(home_odds-away_odds), 2)
                }
                coupons.append(coupon)
                new_coupons += 1
            except Exception as e:
                print(f"[ERROR] Nie można przetworzyć meczu {m.get('home_team','?')} - {m.get('away_team','?')}: {e}")

    save_coupons(coupons)
    print(f"[INFO] Dodano {new_coupons} nowych kuponów")
    send_msg(f"📌 Dodano {new_coupons} nowych kuponów")

# ================= RUN =================
if __name__ == "__main__":
    generate_coupons()