import requests, json, os
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from dateutil import parser

# ================= CONFIG =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS")

# Obsługa wielu kluczy API dla uniknięcia limitów
API_KEYS = [k for k in [
    os.getenv("ODDS_KEY"),
    os.getenv("ODDS_KEY_2"),
    os.getenv("ODDS_KEY_3"),
    os.getenv("ODDS_KEY_4"),
    os.getenv("ODDS_KEY_5")
] if k]

START_BANKROLL = 10000.0
BANKROLL_FILE = "bankroll.json"
COUPONS_FILE = "coupons.json"

# Parametry strategii
MAX_HOURS_AHEAD = 72       # Bot widzi mecze do 3 dni do przodu
VALUE_THRESHOLD = 0.02     # Minimalna przewaga 2%
ODDS_MIN = 1.5             # Minimalny kurs
ODDS_MAX = 10.0            # Maksymalny kurs
MAX_BETS_PER_DAY = 10      # Maksymalna liczba nowych zakładów na dobę

# Obsługiwane ligi
LEAGUES = {
    "basketball_nba": "🏀 NBA",
    "icehockey_nhl": "🏒 NHL",
    "soccer_epl": "⚽ EPL",
    "soccer_germany_bundesliga": "⚽ Bundesliga",
    "soccer_italy_serie_a": "⚽ Serie A",
    "soccer_spain_la_liga": "⚽ La Liga",
    "soccer_france_ligue_one": "⚽ Ligue 1"
}

# Mnożniki bezpieczeństwa dla obliczonej przewagi (Edge)
EDGE_MULTIPLIER = {
    "basketball_nba": 0.90,
    "icehockey_nhl": 0.90,
    "soccer_epl": 0.80,
    "soccer_germany_bundesliga": 0.75,
    "soccer_italy_serie_a": 0.75,
    "soccer_spain_la_liga": 0.75,
    "soccer_france_ligue_one": 0.70
}

# ================= UTILS =================
def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[DEBUG] Błąd ładowania {path}: {e}")
    return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def load_bankroll():
    data = load_json(BANKROLL_FILE, None)
    if not data:
        save_json(BANKROLL_FILE, {"bankroll": START_BANKROLL})
        return START_BANKROLL
    return data.get("bankroll", START_BANKROLL)

def save_bankroll(val):
    save_json(BANKROLL_FILE, {"bankroll": round(val, 2)})

def send_msg(txt, target="types"):
    chat = T_CHAT_RESULTS if target == "results" else T_CHAT
    if not T_TOKEN or not chat:
        print(f"[DEBUG] Telegram skipped:\n{txt}")
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
            json={"chat_id": chat, "text": txt, "parse_mode": "HTML"},
            timeout=10
        )
    except Exception as e:
        print(f"[DEBUG] Telegram error: {e}")

def calc_kelly(bankroll, odds, edge, kelly_frac, max_pct):
    if edge <= 0 or odds <= 1: return 0.0
    # Formula: (Edge / (Kurs - 1)) * Ułamek Kelly'ego
    k = (edge / (odds - 1)) * kelly_frac
    stake = bankroll * k
    stake = max(10.0, stake)  # Minimalna stawka 10 PLN
    stake = min(stake, bankroll * max_pct) # Max 5% bankrolla na zakład
    return round(stake, 2)

def no_vig_probs(odds):
    """Usuwa marżę bukmacherską, aby uzyskać 'sprawiedliwe' prawdopodobieństwo."""
    inv = {k: 1/v for k, v in odds.items() if v}
    s = sum(inv.values())
    return {k: v/s for k, v in inv.items()}

def consensus_odds(odds_list):
    """Oblicza kurs konsensusu z wielu bukmacherów."""
    if len(odds_list) < 2: return None
    mx, mn = max(odds_list), min(odds_list)
    if (mx - mn) / mx > 0.15: return None  # Odrzuć, jeśli rozbieżność > 15%
    return mx

# ================= MAIN RUN =================
def run():
    now = datetime.now(timezone.utc)
    bankroll = load_bankroll()
    coupons = load_json(COUPONS_FILE, [])
    
    # Liczenie aktywności z ostatnich 24h
    daily_bets = sum(1 for c in coupons if parser.isoparse(c["date_time"]) > now - timedelta(days=1))
    print(f"[DEBUG] Start bota. Bankroll: {bankroll} PLN. Dzisiejsze zakłady: {daily_bets}/{MAX_BETS_PER_DAY}")

    for league_key, league_name in LEAGUES.items():
        if daily_bets >= MAX_BETS_PER_DAY: 
            print("[DEBUG] Osiągnięto dobowy limit zakładów.")
            break
        
        print(f"[DEBUG] Analizuję ligę: {league_name}...")
        for key in API_KEYS:
            try:
                r = requests.get(
                    f"https://api.the-odds-api.com/v4/sports/{league_key}/odds",
                    params={"apiKey": key, "markets": "h2h", "regions": "eu"},
                    timeout=15
                )
                
                if r.status_code != 200:
                    print(f"[DEBUG] API Key Error ({r.status_code}) dla {key[:5]}...")
                    continue

                events = r.json()
                print(f"[DEBUG] Pobrano {len(events)} meczów.")

                for e in events:
                    dt = parser.isoparse(e["commence_time"])
                    # Filtr czasu
                    if not (now <= dt <= now + timedelta(hours=MAX_HOURS_AHEAD)):
                        continue

                    # Grupowanie kursów od różnych bukmacherów
                    odds_map = defaultdict(list)
                    for bm in e["bookmakers"]:
                        for m in bm["markets"]:
                            if m["key"] != "h2h": continue
                            for o in m["outcomes"]:
                                odds_map[o["name"]].append(o["price"])

                    odds = {}
                    for name, lst in odds_map.items():
                        val = consensus_odds(lst)
                        if val and ODDS_MIN <= val <= ODDS_MAX:
                            odds[name] = val
                    
                    if len(odds) < 2: continue

                    # Obliczanie Value
                    probs = no_vig_probs(odds)
                    for sel, prob in probs.items():
                        o = odds[sel]
                        # Obliczanie przewagi z uwzględnieniem mnożnika ligi
                        edge = (prob - 1/o) * EDGE_MULTIPLIER.get(league_key, 1)
                        
                        if edge < VALUE_THRESHOLD:
                            if edge > 0.005: # Loguj tylko te bliskie progu
                                print(f"  [INFO] Odrzucono {e['home_team']} ({sel}): Edge {round(edge*100,2)}% < {VALUE_THRESHOLD*100}%")
                            continue

                        # Sprawdzenie czy już nie postawiliśmy na ten mecz
                        if any(c["home"] == e["home_team"] and c["away"] == e["away_team"] for c in coupons):
                            continue

                        # Obliczanie stawki Kelly'ego
                        stake = calc_kelly(bankroll, o, edge, 0.5, 0.05)
                        if stake <= 0 or bankroll < stake:
                            continue

                        # REJESTRACJA ZAKŁADU
                        bankroll -= stake
                        save_bankroll(bankroll)
                        possible_win = round(stake * o, 2)

                        new_coupon = {
                            "league": league_key,
                            "league_name": league_name,
                            "home": e["home_team"],
                            "away": e["away_team"],
                            "pick": sel,
                            "odds": o,
                            "stake": stake,
                            "possible_win": possible_win,
                            "status": "pending",
                            "date_time": dt.isoformat()
                        }
                        coupons.append(new_coupon)

                        print(f"✅ ZAKŁAD: {e['home_team']} vs {e['away_team']} | {sel} @{o}")
                        
                        send_msg(
                            f"⚔️ <b>VALUE BET • {league_name}</b>\n"
                            f"{e['home_team']} vs {e['away_team']}\n"
                            f"🎯 Typ: <b>{sel}</b>\n"
                            f"📈 Kurs: <b>{o}</b>\n"
                            f"💎 Edge: {round(edge*100,2)}%\n"
                            f"💰 Stawka: {stake} PLN\n"
                            f"🗓️ {dt.strftime('%m-%d %H:%M UTC')}"
                        )

                        daily_bets += 1
                        if daily_bets >= MAX_BETS_PER_DAY: break
                
                break # Jeśli klucz zadziałał i pobrał dane, przejdź do następnej ligi
            except Exception as ex:
                print(f"[ERROR] Błąd przetwarzania ligi: {ex}")
                continue

    save_json(COUPONS_FILE, coupons)
    print(f"[DEBUG] Koniec sesji. Bankroll: {bankroll} PLN")

if __name__ == "__main__":
    run()
