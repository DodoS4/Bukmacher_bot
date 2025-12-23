import requests
import os
import time
import sqlite3
from datetime import datetime, timedelta, timezone

# --- CONFIG ---
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")

API_KEYS = [k for k in [
    os.getenv("ODDS_KEY"),
    os.getenv("ODDS_KEY_2"),
    os.getenv("ODDS_KEY_3"),
    os.getenv("ODDS_KEY_4")
] if k]

SPORTS = {
    "soccer_epl": "⚽ PREMIER LEAGUE",
    "soccer_spain_la_liga": "⚽ LA LIGA",
    "soccer_germany_bundesliga": "⚽ BUNDESLIGA",
    "soccer_italy_serie_a": "⚽ SERIE A",
    "soccer_poland_ekstraklasa": "⚽ EKSTRAKLASA",
    "basketball_nba": "🏀 NBA",
    "icehockey_nhl": "🏒 NHL"
}

DB = "sent.db"

# --- HELPERS ---
def esc(t: str) -> str:
    return t.replace("_", "\\_").replace("*", "\\*").replace("(", "\\(").replace(")", "\\)")

# --- RADAR ---
class Radar:
    def __init__(self):
        self.session = requests.Session()
        self.db = sqlite3.connect(DB)
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS sent (
                match_id TEXT,
                category TEXT,
                date TEXT,
                PRIMARY KEY (match_id, category)
            )
        """)
        self.db.commit()

    def sent(self, mid, cat):
        q = self.db.execute(
            "SELECT 1 FROM sent WHERE match_id=? AND category=?",
            (mid, cat)
        ).fetchone()
        return q is not None

    def mark(self, mid, cat):
        self.db.execute(
            "INSERT OR IGNORE INTO sent VALUES (?, ?, ?)",
            (mid, cat, datetime.utcnow().date().isoformat())
        )
        self.db.commit()

    def send(self, txt):
        url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
        self.session.post(url, json={
            "chat_id": T_CHAT,
            "text": txt,
            "parse_mode": "Markdown"
        }, timeout=10)

    def fetch(self, sport):
        for k in API_KEYS:
            try:
                r = self.session.get(
                    f"https://api.the-odds-api.com/v4/sports/{sport}/odds",
                    params={"apiKey": k, "regions": "eu", "markets": "h2h"},
                    timeout=10
                )
                if r.status_code == 200:
                    return r.json()
            except:
                pass
        return []

    def avg_without_max(self, odds):
        m = max(odds)
        f = [o for o in odds if o != m]
        return sum(f)/len(f) if f else sum(odds)/len(odds)

    def run(self):
        now = datetime.now(timezone.utc)
        limit = now + timedelta(days=3)

        for sport, label in SPORTS.items():
            for m in self.fetch(sport):
                mid = m["id"]
                dt = datetime.strptime(
                    m["commence_time"], "%Y-%m-%dT%H:%M:%SZ"
                ).replace(tzinfo=timezone.utc)
                if dt > limit:
                    continue

                home = esc(m["home_team"])
                away = esc(m["away_team"])

                h, a, d = [], [], []

                for bm in m["bookmakers"]:
                    for mk in bm["markets"]:
                        if mk["key"] != "h2h":
                            continue
                        try:
                            h.append(next(o["price"] for o in mk["outcomes"] if o["name"] == m["home_team"]))
                            a.append(next(o["price"] for o in mk["outcomes"] if o["name"] == m["away_team"]))
                            draw = next((o["price"] for o in mk["outcomes"] if o["name"].lower() == "draw"), None)
                            if draw:
                                d.append(draw)
                        except:
                            pass

                if not h or not a:
                    continue

                max_h, max_a = max(h), max(a)
                avg_h = self.avg_without_max(h)
                avg_a = self.avg_without_max(a)

                # --- SUREBET ---
                if d:
                    margin = (1/max_h) + (1/max_a) + (1/max(d))
                else:
                    margin = (1/max_h) + (1/max_a)

                if margin < 1.0 and not self.sent(mid, "surebet"):
                    profit = (1 - margin) * 100
                    msg = (
                        f"🚀 *SUREBET*\n🏆 {label}\n"
                        f"💰 +{profit:.2f}%\n\n"
                        f"🏠 `{max_h:.2f}`\n✈️ `{max_a:.2f}`"
                    )
                    self.send(msg)
                    self.mark(mid, "surebet")
                    continue

                # --- VALUE (bez draw) ---
                if not d:
                    if max_h > avg_h * 1.25 and not self.sent(mid, "mega"):
                        self.send(f"🔥 *MEGA VALUE*\n🏆 {label}\n✅ *{home}* `{max_h:.2f}`")
                        self.mark(mid, "mega")
                        continue

                    if max_a > avg_a * 1.25 and not self.sent(mid, "mega"):
                        self.send(f"🔥 *MEGA VALUE*\n🏆 {label}\n✅ *{away}* `{max_a:.2f}`")
                        self.mark(mid, "mega")
                        continue

                    if max_h > avg_h * 1.12 and not self.sent(mid, "value"):
                        self.send(f"💎 *VALUE*\n🏆 {label}\n✅ *{home}* `{max_h:.2f}`")
                        self.mark(mid, "value")
                        continue

                    if max_a > avg_a * 1.12 and not self.sent(mid, "value"):
                        self.send(f"💎 *VALUE*\n🏆 {label}\n✅ *{away}* `{max_a:.2f}`")
                        self.mark(mid, "value")
                        continue

                # --- PEWNIAK ---
                fav = min(avg_h, avg_a)
                if fav <= 1.70 and not self.sent(mid, "daily"):
                    pick = home if avg_h < avg_a else away
                    tag = "🔥 *PEWNIAK*" if fav <= 1.30 else "⭐ *WARTE UWAGI*"
                    self.send(f"{tag}\n🏆 {label}\n✅ *{pick}* `{fav:.2f}`")
                    self.mark(mid, "daily")

            time.sleep(1)


if __name__ == "__main__":
    Radar().run()
