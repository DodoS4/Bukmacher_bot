import requests
import json
import os
from datetime import datetime, timedelta, timezone
from dateutil import tz
from collections import defaultdict

# ================= KONFIGURACJA ZYSKU =================
TAX_PL = 0.88          # Uwzględniamy podatek 12%
MIN_VALUE_NETTO = 0.03  # Minimum 3% zysku na czysto (po podatku)
BASE_STAKE = 250        # Stawka pod cel 5000 zł
MIN_BOOKIES = 3         # Wiarygodność danych

API_KEYS = [os.getenv(f"ODDS_KEY_{i}") for i in range(1, 6) if os.getenv(f"ODDS_KEY_{i}")]
if not API_KEYS:
    main_key = os.getenv("ODDS_KEY")
    API_KEYS = [main_key] if main_key else []

# Twoje emoji i ligi
SPORTS_CONFIG = {
    "basketball_nba": "🏀", "icehockey_nhl": "🏒", "soccer_epl": "⚽",
    "soccer_spain_la_liga": "🇪🇸", "soccer_germany_bundesliga": "🇩🇪",
    "soccer_italy_serie_a": "🇮🇹", "soccer_france_ligue_one": "🇫🇷",
    "soccer_poland_ekstraklasa": "🇵🇱"
}

COUPON_FILE = "coupons.json"

def send_telegram(message):
    token = os.getenv("T_TOKEN")
    chat = os.getenv("T_CHAT")
    if not token or not chat: return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        requests.post(url, json={"chat_id": chat, "text": message, "parse_mode": "HTML", "disable_web_page_preview": True})
    except: pass

def get_data(sport):
    for key in API_KEYS:
        url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
        params = {'apiKey': key, 'regions': 'eu', 'markets': 'h2h'}
        try:
            resp = requests.get(url, params=params, timeout=15)
            if resp.status_code == 200: return resp.json()
            if resp.status_code == 429: continue
        except: continue
    return []

def main():
    now = datetime.now(timezone.utc)
    
    # Wczytywanie bazy, by uniknąć duplikatów
    if os.path.exists(COUPON_FILE):
        try:
            with open(COUPON_FILE, "r", encoding="utf-8") as f:
                coupons = json.load(f)
        except: coupons = []
    else: coupons = []

    for sport, icon in SPORTS_CONFIG.items():
        matches = get_data(sport)
        for m in matches:
            match_id = m["id"]
            
            # Grupowanie kursów wszystkich bukmacherów
            odds_pool = defaultdict(list)
            for bm in m.get("bookmakers", []):
                for market in bm.get("markets", []):
                    for outcome in market.get("outcomes", []):
                        odds_pool[outcome["name"]].append(outcome["price"])

            # Logika wyboru faworyta matematycznego
            for sel, prices in odds_pool.items():
                if len(prices) < MIN_BOOKIES: continue
                
                max_o = max(prices)  # Najlepszy kurs jaki możesz zagrać
                avg_o = sum(prices) / len(prices)  # Średnia rynkowa (cena sprawiedliwa)
                
                # Obliczamy szansę na podstawie średniej
                fair_prob = 1 / avg_o
                # Obliczamy zysk po odjęciu podatku
                ev_netto = (fair_prob * (max_o * TAX_PL)) - 1

                if ev_netto >= MIN_VALUE_NETTO:
                    # Sprawdzanie czy już wysłano
                    if any(c.get("id") == match_id and c.get("pick") == sel for c in coupons):
                        continue

                    # Twój ulubiony wygląd wiadomości
                    pl_zone = tz.gettz('Europe/Warsaw')
                    date_str = datetime.fromisoformat(m["commence_time"].replace("Z", "+00:00")).astimezone(pl_zone).strftime("%d.%m | %H:%M")

                    msg = (
                        f"{icon} <b>{m['sport_title'].upper()}</b>\n"
                        f"━━━━━━━━━━━━━━━\n"
                        f"🏟 <b>{m['home_team']}</b> vs <b>{m['away_team']}</b>\n"
                        f"⏰ Start: <code>{date_str}</code>\n\n"
                        f"✅ Typ: <b>{sel}</b>\n"
                        f"📈 Kurs: <b>{max_o:.2f}</b> (EV: +{round(ev_netto*100, 1)}%)\n"
                        f"💰 Stawka: <b>{BASE_STAKE} PLN</b>\n"
                        f"━━━━━━━━━━━━━━━"
                    )
                    send_telegram(msg)
                    
                    coupons.append({
                        "id": match_id, "time": m["commence_time"],
                        "home": m["home_team"], "away": m["away_team"],
                        "pick": sel, "odds": max_o, "status": "PENDING"
                    })

    # Czyszczenie starych rekordów
    coupons = [c for c in coupons if datetime.fromisoformat(c["time"].replace("Z", "+00:00")) > now - timedelta(hours=6)]
    with open(COUPON_FILE, "w", encoding="utf-8") as f:
        json.dump(coupons, f, indent=4, ensure_ascii=False)

if __name__ == "__main__":
    main()
