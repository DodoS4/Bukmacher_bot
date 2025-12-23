import requests
import os
import time
from datetime import datetime, timedelta, timezone

# --- KONFIGURACJA ---
T_TOKEN = os.getenv('T_TOKEN')
T_CHAT = os.getenv('T_CHAT')

KEYS_POOL = [
    os.getenv('ODDS_KEY'),
    os.getenv('ODDS_KEY_2'),
    os.getenv('ODDS_KEY_3'),
    os.getenv('ODDS_KEY_4')
]
API_KEYS = [k for k in KEYS_POOL if k]

SPORTS_CONFIG = {
    'soccer_epl': '⚽ PREMIER LEAGUE',
    'soccer_spain_la_liga': '⚽ LA LIGA',
    'soccer_germany_bundesliga': '⚽ BUNDESLIGA',
    'soccer_italy_serie_a': '⚽ SERIE A',
    'soccer_poland_ekstraklasa': '⚽ EKSTRAKLASA',
    'basketball_nba': '🏀 NBA',
    'icehockey_nhl': '🏒 NHL',
    'mma_mixed_martial_arts': '🥊 MMA/UFC'
}

DB_FILE = "sent_matches.txt"


# --- FUNKCJE POMOCNICZE ---
def send_msg(text):
    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
    payload = {
        "chat_id": T_CHAT,
        "text": text,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print("Telegram error:", e)


def is_already_sent(match_id, category):
    key = f"{match_id}_{category}"
    if not os.path.exists(DB_FILE):
        open(DB_FILE, "w").close()
        return False
    with open(DB_FILE, "r") as f:
        return key in f.read().splitlines()


def mark_as_sent(match_id, category):
    with open(DB_FILE, "a") as f:
        f.write(f"{match_id}_{category}\n")


def fetch_odds(sport_key):
    for i, key in enumerate(API_KEYS):
        url = (
            f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/"
            f"?apiKey={key}&regions=eu&markets=h2h"
        )
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 429:
                print(f"⚠️ Klucz {i+1} limit — zmiana")
        except Exception as e:
            print("API error:", e)
    return None


def calculate_ev(avg_odds, best_odds):
    return (best_odds * (1 / avg_odds)) - 1


# --- GŁÓWNA LOGIKA ---
def run_pro_radar():
    if not API_KEYS:
        print("❌ Brak kluczy API")
        return

    now = datetime.now(timezone.utc)
    limit_date = now + timedelta(days=3)

    if now.hour == 0 or os.getenv("GITHUB_EVENT_NAME") == "workflow_dispatch":
        send_msg(
            "🟢 *STATUS: AKTYWNY*\n"
            f"🔑 Klucze API: `{len(API_KEYS)}`\n"
            "🤖 Tryb: VALUE + PEWNIAKI + 3 SUPER OKAZJE"
        )

    super_values = []

    for sport_key, sport_label in SPORTS_CONFIG.items():
        data = fetch_odds(sport_key)
        if not data:
            continue

        for match in data:
            try:
                match_id = match["id"]
                home = match["home_team"]
                away = match["away_team"]
                match_time = datetime.strptime(
                    match["commence_time"], "%Y-%m-%dT%H:%M:%SZ"
                ).replace(tzinfo=timezone.utc)
            except:
                continue

            if match_time > limit_date:
                continue

            all_home, all_away = [], []

            for bm in match.get("bookmakers", []):
                for market in bm.get("markets", []):
                    if market.get("key") == "h2h" and len(market.get("outcomes", [])) == 2:
                        try:
                            h = next(o["price"] for o in market["outcomes"] if o["name"] == home)
                            a = next(o["price"] for o in market["outcomes"] if o["name"] == away)
                            all_home.append(h)
                            all_away.append(a)
                        except:
                            continue

            if len(all_home) < 3:
                continue

            avg_h = sum(all_home) / len(all_home)
            avg_a = sum(all_away) / len(all_away)
            max_h = max(all_home)
            max_a = max(all_away)

            # --- BUKMACHER ZASPAŁ ---
            if not is_already_sent(match_id, "value"):
                if max_h > avg_h * 1.12:
                    send_msg(
                        f"💎 *BUKMACHER ZASPAŁ!*\n"
                        f"🏆 {sport_label}\n"
                        f"━━━━━━━━━━━━━━━\n"
                        f"✅ *{home.upper()}*\n"
                        f"📈 Kurs: `{max_h:.2f}`\n"
                        f"📊 Średnia: `{avg_h:.2f}`"
                    )
                    mark_as_sent(match_id, "value")

                elif max_a > avg_a * 1.12:
                    send_msg(
                        f"💎 *BUKMACHER ZASPAŁ!*\n"
                        f"🏆 {sport_label}\n"
                        f"━━━━━━━━━━━━━━━\n"
                        f"✅ *{away.upper()}*\n"
                        f"📈 Kurs: `{max_a:.2f}`\n"
                        f"📊 Średnia: `{avg_a:.2f}`"
                    )
                    mark_as_sent(match_id, "value")

            # --- PEWNIAKI ---
            min_avg = min(avg_h, avg_a)
            if min_avg <= 1.75 and not is_already_sent(match_id, "daily"):
                tag = "🔥 *PEWNIAK*" if min_avg <= 1.35 else "⭐ *WARTE UWAGI*"
                send_msg(
                    f"{tag}\n"
                    f"🏆 {sport_label}\n"
                    f"━━━━━━━━━━━━━━━\n"
                    f"{home}: `{avg_h:.2f}`\n"
                    f"{away}: `{avg_a:.2f}`\n"
                    f"━━━━━━━━━━━━━━━\n"
                    f"⏰ `{match_time.strftime('%d.%m %H:%M')}` UTC"
                )
                mark_as_sent(match_id, "daily")

            # --- SUPER OKAZJE (EV) ---
            ev_h = calculate_ev(avg_h, max_h)
            ev_a = calculate_ev(avg_a, max_a)

            if ev_h > ev_a:
                ev, pick, odds, avg = ev_h, home, max_h, avg_h
            else:
                ev, pick, odds, avg = ev_a, away, max_a, avg_a

            if ev >= 0.08:
                super_values.append({
                    "id": match_id,
                    "sport": sport_label,
                    "pick": pick,
                    "odds": odds,
                    "avg": avg,
                    "ev": ev,
                    "time": match_time
                })

        time.sleep(1)

    # --- TOP 3 SUPER OKAZJE ---
    top3 = sorted(super_values, key=lambda x: x["ev"], reverse=True)[:3]

    for i, bet in enumerate(top3, start=1):
        if is_already_sent(bet["id"], "super"):
            continue

        send_msg(
            f"🚀 *SUPER OKAZJA #{i}*\n"
            f"🏆 {bet['sport']}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"✅ *{bet['pick'].upper()}*\n\n"
            f"💰 Kurs: `{bet['odds']:.2f}`\n"
            f"📊 Średnia: `{bet['avg']:.2f}`\n"
            f"📈 EV: `+{bet['ev']*100:.1f}%`\n"
            f"━━━━━━━━━━━━━━━\n"
            f"⏰ `{bet['time'].strftime('%d.%m %H:%M')}` UTC"
        )
        mark_as_sent(bet["id"], "super")


if __name__ == "__main__":
    run_pro_radar()
