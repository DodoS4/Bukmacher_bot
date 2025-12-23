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

LIQUID_BOOKMAKERS = ["pinnacle", "bet365", "williamhill", "ladbrokes", "marathonbet"]

DB = "sent.db"

# --- HELPERS ---
def esc(t: str) -> str:
    return t.replace("_", "\\_").replace("*", "\\*").replace("(", "\\(").replace(")", "\\)")

def implied_probability(odds):
    return 1 / odds if odds else 0

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
                stake REAL,
                odds REAL,
                result TEXT,
                roi REAL,
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

    def mark(self, mid, cat, stake=None, odds=None, result=None, roi=None):
        self.db.execute(
            """INSERT OR REPLACE INTO sent VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (mid, cat, datetime.utcnow().date().isoformat(), stake, odds, result, roi)
        )
        self.db.commit()

    def update_result(self, mid, cat, result):
        row = self.db.execute(
            "SELECT stake, odds FROM sent WHERE match_id=? AND category=?",
            (mid, cat)
        ).fetchone()
        if not row:
            return
        stake, odds = row
        if stake is None or odds is None:
            stake, odds = 1, 1  # domyślnie 1 jednostka
        if result == "win":
            roi = stake * (odds - 1)
        elif result == "loss":
            roi = -stake
        else:  # void
            roi = 0
        self.db.execute(
            "UPDATE sent SET result=?, roi=? WHERE match_id=? AND category=?",
            (result, roi, mid, cat)
        )
        self.db.commit()

    def send(self, txt, buttons=None):
        url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
        data = {"chat_id": T_CHAT, "text": txt, "parse_mode": "Markdown"}
        if buttons:
            data["reply_markup"] = {"inline_keyboard": buttons}
        self.session.post(url, json=data, timeout=10)

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

    def weighted_avg(self, odds_list, bookmakers_list):
        filtered = [o for o, bm in zip(odds_list, bookmakers_list) if bm.lower() in LIQUID_BOOKMAKERS]
        return sum(filtered)/len(filtered) if filtered else sum(odds_list)/len(odds_list)

    def run(self):
        now = datetime.now(timezone.utc)
        limit = now + timedelta(days=3)

        for sport, label in SPORTS.items():
            for m in self.fetch(sport):
                mid = m["id"]
                dt = datetime.strptime(m["commence_time"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                if dt > limit:
                    continue

                home = esc(m["home_team"])
                away = esc(m["away_team"])

                h, a, d = [], [], []
                bookmakers = []

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
                            bookmakers.append(bm["key"])
                        except:
                            pass

                if not h or not a:
                    continue

                max_h, max_a = max(h), max(a)
                max_d = max(d) if d else None

                avg_h = self.weighted_avg(h, bookmakers)
                avg_a = self.weighted_avg(a, bookmakers)
                avg_d = self.weighted_avg(d, bookmakers) if max_d else None

                ip_h = implied_probability(max_h)
                ip_a = implied_probability(max_a)
                ip_d = implied_probability(max_d) if max_d else 0

                tv_h = ip_h - implied_probability(avg_h)
                tv_a = ip_a - implied_probability(avg_a)
                tv_d = ip_d - implied_probability(avg_d) if avg_d else None

                # --- SUREBET ---
                if max_d:
                    margin = (1/max_h) + (1/max_a) + (1/max_d)
                else:
                    margin = (1/max_h) + (1/max_a)

                if margin < 1.0 and not self.sent(mid, "surebet"):
                    profit = (1 - margin) * 100
                    buttons = [
                        [{"text": "✅ Win", "callback_data": f"{mid}|surebet|win"}],
                        [{"text": "❌ Loss", "callback_data": f"{mid}|surebet|loss"}],
                        [{"text": "⚠️ Void", "callback_data": f"{mid}|surebet|void"}]
                    ]
                    msg = f"🚀 *SUREBET*\n🏆 {label}\n💰 +{profit:.2f}%\n🏠 `{max_h:.2f}`\n✈️ `{max_a:.2f}`"
                    if max_d:
                        msg += f"\n🤝 `{max_d:.2f}`"
                    self.send(msg, buttons)
                    self.mark(mid, "surebet", stake=1, odds=max(max_h, max_a, max_d if max_d else 0))
                    continue

                # --- VALUE ALERT (True Value > 12%, bez draw) ---
                if not d:
                    if tv_h > 0.12 and not self.sent(mid, "mega"):
                        buttons = [
                            [{"text": "✅ Win", "callback_data": f"{mid}|mega|win"}],
                            [{"text": "❌ Loss", "callback_data": f"{mid}|mega|loss"}],
                            [{"text": "⚠️ Void", "callback_data": f"{mid}|mega|void"}]
                        ]
                        self.send(f"🔥 *MEGA VALUE*\n🏆 {label}\n✅ *{home}* `{max_h:.2f}`", buttons)
                        self.mark(mid, "mega", stake=1, odds=max_h)
                        continue
                    if tv_a > 0.12 and not self.sent(mid, "mega"):
                        buttons = [
                            [{"text": "✅ Win", "callback_data": f"{mid}|mega|win"}],
                            [{"text": "❌ Loss", "callback_data": f"{mid}|mega|loss"}],
                            [{"text": "⚠️ Void", "callback_data": f"{mid}|mega|void"}]
                        ]
                        self.send(f"🔥 *MEGA VALUE*\n🏆 {label}\n✅ *{away}* `{max_a:.2f}`", buttons)
                        self.mark(mid, "mega", stake=1, odds=max_a)
                        continue

                # --- PEWNIAK ---
                fav = min(avg_h, avg_a)
                if fav <= 1.70 and not self.sent(mid, "daily"):
                    pick = home if avg_h < avg_a else away
                    tag = "🔥 *PEWNIAK*" if fav <= 1.30 else "⭐ *WARTE UWAGI*"
                    buttons = [
                        [{"text": "✅ Win", "callback_data": f"{mid}|daily|win"}],
                        [{"text": "❌ Loss", "callback_data": f"{mid}|daily|loss"}],
                        [{"text": "⚠️ Void", "callback_data": f"{mid}|daily|void"}]
                    ]
                    self.send(f"{tag}\n🏆 {label}\n✅ *{pick}* `{fav:.2f}`", buttons)
                    self.mark(mid, "daily", stake=1, odds=fav)

            time.sleep(1)


if __name__ == "__main__":
    Radar().run()
