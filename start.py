import requests
import os
from datetime import datetime, timezone

# ================= CONFIG =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS")
API_KEYS = [k for k in [
    os.getenv("ODDS_KEY"),
    os.getenv("ODDS_KEY_2"),
    os.getenv("ODDS_KEY_3"),
    os.getenv("ODDS_KEY_4"),
    os.getenv("ODDS_KEY_5")
] if k]

MAX_HOURS_AHEAD = 72  # okno 72h

# ================= LIGI DOSTĘPNE DLA KLUCZA =================
LEAGUES = [
    "basketball_nba",
    "basketball_euroleague",
    "icehockey_nhl",
    "soccer_epl",
    "soccer_efl_champ",
    "soccer_germany_bundesliga",
    "soccer_italy_serie_a",
    "soccer_spain_la_liga",
    "soccer_france_ligue_one",
    "soccer_uefa_champs_league"
]

LEAGUE_INFO = {
    "basketball_nba": {"name": "NBA", "flag": "🏀"},
    "basketball_euroleague": {"name": "Euroliga", "flag": "🏀"},
    "icehockey_nhl": {"name": "NHL", "flag": "🏒"},
    "soccer_epl": {"name": "Premier League", "flag": "🏴"},
    "soccer_efl_champ": {"name": "Championship", "flag": "🏴"},
    "soccer_germany_bundesliga": {"name": "Bundesliga", "flag": "🇩🇪"},
    "soccer_italy_serie_a": {"name": "Serie A", "flag": "🇮🇹"},
    "soccer_spain_la_liga": {"name": "La Liga", "flag": "🇪🇸"},
    "soccer_france_ligue_one": {"name": "Ligue 1", "flag": "🇫🇷"},
    "soccer_uefa_champs_league": {"name": "Champions League", "flag": "🏆"}
}

# ================= TELEGRAM =================
def send_msg(text):
    if not T_TOKEN or not T_CHAT_RESULTS:
        print("Telegram not configured. Message:\n", text)
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
            json={"chat_id": T_CHAT_RESULTS, "text": text, "parse_mode": "HTML"},
            timeout=10
        )
    except Exception as e:
        print("Telegram send failed:", e)

# ================= SCAN OFFERS =================
def scan_offers():
    total_scanned = 0
    report = "🔍 Skanowanie ofert – BEZ FILTRÓW\n━━━━━━━━━━━━━━\n"

    for league in LEAGUES:
        league_ok = False
        for key in API_KEYS:
            try:
                r = requests.get(
                    f"https://api.the-odds-api.com/v4/sports/{league}/odds",
                    params={"apiKey": key, "daysFrom": MAX_HOURS_AHEAD},
                    timeout=10
                )
                if r.status_code != 200:
                    continue

                data = r.json()
                if not data:
                    continue

                league_ok = True
                total_scanned += len(data)
                report += f"✅ {league}: {len(data)} meczów\n"

                for game in data:
                    home = game.get("home_team", "")
                    away = game.get("away_team", "")
                    markets = game.get("bookmakers", [])
                    # pokazujemy główne kursy z pierwszego bukmachera
                    odds_text = ""
                    if markets:
                        odds_texts = []
                        for m in markets[:1]:  # tylko pierwszy bookmaker
                            for market in m.get("markets", []):
                                for outcome in market.get("outcomes", []):
                                    odds_texts.append(f"{outcome['name']}:{outcome['price']}")
                        odds_text = ", ".join(odds_texts)
                    report += f"    ➤ {home} vs {away} | {odds_text}\n"
                break
            except Exception as e:
                print(f"Błąd przy {league}: {e}")
                continue

        if not league_ok:
            report += f"❌ {league}: niedostępna\n"

    report += f"\nZeskanowano: {total_scanned} meczów"
    send_msg(report)

# ================= RUN =================
if __name__ == "__main__":
    scan_offers()