import requests
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from dateutil import parser
import logging
from logging.handlers import RotatingFileHandler
from shutil import copy2

# ================= LOGGING =================
def setup_logging():
    logger = logging.getLogger('betting_bot')
    logger.setLevel(logging.INFO)
    
    # Plik z rotacją (max 5MB, 3 backupy)
    handler = RotatingFileHandler(
        'betting_bot.log', 
        maxBytes=5*1024*1024, 
        backupCount=3,
        encoding='utf-8'
    )
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    # Też do konsoli
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)
    
    return logger

logger = setup_logging()

# ================= CONFIG =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS")

API_KEYS = [k for k in [
    os.getenv("ODDS_KEY"),
    os.getenv("ODDS_KEY_2"),
    os.getenv("ODDS_KEY_3")
] if k]

COUPONS_FILE = "coupons.json"
BANKROLL_FILE = "bankroll.json"
API_USAGE_FILE = "api_usage.json"
START_BANKROLL = 400.0

MAX_HOURS_AHEAD = 48  # 48 godzin do przodu
VALUE_THRESHOLD = 0.035
KELLY_FRACTION = 0.25

# Limity bezpieczeństwa
DAILY_LOSS_LIMIT = 20.0  # Max strata dziennie
MAX_BETS_PER_DAY = 10    # Max zakładów dziennie
MIN_BANKROLL = 50.0      # Zatrzymaj się poniżej tego
MAX_ODDS_LIMIT = 50.0    # Max akceptowany kurs
MIN_ODDS_ABSOLUTE = 1.01 # Min akceptowany kurs
MAX_MARGIN = 0.15        # Max akceptowalna marża (15%)

# ================= LIGI =================
LEAGUES = [
    "basketball_nba",
    "soccer_epl",
    "icehockey_nhl",
    "soccer_poland_ekstraklasa",
    "soccer_uefa_champs_league"
]

LEAGUE_INFO = {
    "basketball_nba": {"name": "NBA", "flag": "🏀"},
    "soccer_epl": {"name": "Premier League", "flag": "⚽ PL"},
    "icehockey_nhl": {"name": "NHL", "flag": "🏒"},
    "soccer_poland_ekstraklasa": {"name": "Ekstraklasa", "flag": "⚽ EK"},
    "soccer_uefa_champs_league": {"name": "Champions League", "flag": "🏆 CL"}
}

MIN_ODDS = {
    "basketball_nba": 1.8,
    "icehockey_nhl": 2.3,
    "soccer_epl": 2.5,
    "soccer_poland_ekstraklasa": 2.5,
    "soccer_uefa_champs_league": 2.5
}

# ================= FILE UTILS =================
def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Błąd wczytywania {path}: {e}")
    return default

def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Błąd zapisywania {path}: {e}")

# ================= BACKUP =================
def backup_data():
    """Tworzy backup przed zmianami"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    for file in [COUPONS_FILE, BANKROLL_FILE]:
        if os.path.exists(file):
            try:
                backup_name = f"{file}.backup_{timestamp}"
                copy2(file, backup_name)
                logger.info(f"Utworzono backup: {backup_name}")
            except Exception as e:
                logger.error(f"Błąd tworzenia backupu {file}: {e}")
    
    cleanup_old_backups()

def cleanup_old_backups():
    """Usuwa backupy starsze niż 7 dni"""
    try:
        for file in os.listdir('.'):
            if '.backup_' in file:
                try:
                    backup_date = file.split('_')[-2]
                    backup_time = datetime.strptime(backup_date, "%Y%m%d")
                    if datetime.now() - backup_time > timedelta(days=7):
                        os.remove(file)
                        logger.info(f"Usunięto stary backup: {file}")
                except:
                    pass
    except Exception as e:
        logger.error(f"Błąd czyszczenia backupów: {e}")

# ================= BANKROLL =================
def load_bankroll():
    return load_json(BANKROLL_FILE, {}).get("bankroll", START_BANKROLL)

def save_bankroll(val):
    save_json(BANKROLL_FILE, {"bankroll": round(val, 2)})

def calc_kelly_stake(bankroll, odds, edge):
    if edge <= 0 or odds <= 1:
        return 0.0
    b = odds - 1
    kelly = edge / b
    stake = bankroll * kelly * KELLY_FRACTION
    stake = max(3.0, stake)
    stake = min(stake, bankroll * 0.05)
    return round(stake, 2)

# ================= API USAGE TRACKING =================
def track_api_call(key):
    """Śledzi wywołania API aby nie przekroczyć limitów"""
    usage = load_json(API_USAGE_FILE, {})
    today = str(datetime.now(timezone.utc).date())
    
    if today not in usage:
        usage = {today: {}}
    
    usage[today][key] = usage[today].get(key, 0) + 1
    save_json(API_USAGE_FILE, usage)
    
    # Ostrzeżenie jeśli blisko limitu (500 requestów/dzień)
    if usage[today][key] > 450:
        logger.warning(f"API key {key[:8]}... używany {usage[today][key]} razy dzisiaj!")
        send_msg(f"⚠️ API key {key[:8]}... blisko limitu: {usage[today][key]}/500", target="results")
    
    return usage[today][key]

# ================= LIMITS CHECK =================
def check_limits(coupons, bankroll):
    """Sprawdza czy nie przekroczono limitów"""
    today = str(datetime.now(timezone.utc).date())
    today_coupons = [c for c in coupons if c.get("sent_date") == today]
    
    # Ile zakładów dzisiaj
    if len(today_coupons) >= MAX_BETS_PER_DAY:
        logger.warning(f"Osiągnięto limit zakładów dziennych: {len(today_coupons)}/{MAX_BETS_PER_DAY}")
        return False
    
    # Jaka strata dzisiaj
    daily_loss = sum(c.get("stake", 0) for c in today_coupons if c["status"] == "lost")
    daily_profit = sum(c.get("win_val", 0) for c in today_coupons if c["status"] == "won")
    net = daily_profit - daily_loss
    
    if net < -DAILY_LOSS_LIMIT:
        logger.warning(f"Przekroczono dzienny limit strat: {net} PLN")
        send_msg(f"🛑 <b>STOP</b> - Przekroczono dzienny limit strat: {net} PLN", target="results")
        return False
    
    # Czy bankroll nie za niski
    if bankroll < MIN_BANKROLL:
        logger.warning(f"Bankroll za niski: {bankroll} PLN")
        send_msg(f"🛑 <b>STOP</b> - Bankroll poniżej minimum: {bankroll} PLN", target="results")
        return False
    
    return True

# ================= TELEGRAM =================
def send_msg(text, target="types"):
    chat_id = T_CHAT_RESULTS if target == "results" else T_CHAT
    if not T_TOKEN or not chat_id:
        logger.warning("Brak konfiguracji Telegram")
        return
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            },
            timeout=10
        )
        if response.status_code != 200:
            logger.error(f"Błąd wysyłania wiadomości Telegram: {response.status_code}")
    except Exception as e:
        logger.error(f"Błąd wysyłania do Telegram: {e}")

# ================= FORMAT UI =================
def format_match_time(dt):
    return dt.strftime("%d.%m.%Y • %H:%M UTC")

def format_value_card(league_key, home, away, dt, pick, odds, edge, stake):
    info = LEAGUE_INFO.get(league_key, {"name": league_key, "flag": "🎯"})
    tier = "A" if edge >= 0.08 else "B"
    return (
        f"{info['flag']} <b>VALUE BET • {info['name']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"<b>{home} vs {away}</b>\n"
        f"🕒 {format_match_time(dt)}\n"
        f"🎯 Typ: <b>{pick}</b>\n"
        f"📈 Kurs: <b>{odds}</b>\n"
        f"💎 Edge: <b>+{round(edge*100,2)}%</b>\n"
        f"🏷 Tier: <b>{tier}</b>\n"
        f"💰 Stawka: <b>{stake} PLN</b>"
    )

# ================= ODDS VALIDATION =================
def validate_odds(odds_data, league):
    """Sprawdza czy kursy są rozsądne"""
    issues = []
    
    # Sprawdź czy kursy nie są za niskie/wysokie
    for team, odds in odds_data.items():
        if odds and (odds < MIN_ODDS_ABSOLUTE or odds > MAX_ODDS_LIMIT):
            issues.append(f"Podejrzany kurs dla {team}: {odds}")
    
    # Sprawdź czy marża nie jest za wysoka
    valid_odds = [o for o in odds_data.values() if o]
    if len(valid_odds) >= 2:
        margin = sum(1/o for o in valid_odds) - 1
        if margin > MAX_MARGIN:
            issues.append(f"Wysoka marża: {margin*100:.2f}%")
    
    if issues:
        logger.warning(f"Problemy z kursami w {league}: {issues}")
        return False
    return True

# ================= ODDS =================
def no_vig_probs(odds):
    inv = {k: 1/v for k, v in odds.items() if v}
    s = sum(inv.values())
    if s == 0:
        return {}
    return {k: v/s for k, v in inv.items()}

def generate_pick(match):
    h_o = match["odds"]["home"]
    a_o = match["odds"]["away"]
    d_o = match["odds"].get("draw")

    if match["league"] == "icehockey_nhl":
        probs = no_vig_probs({"home": h_o, "away": a_o})
        p = {match["home"]: probs.get("home", 0), match["away"]: probs.get("away", 0)}
    else:
        probs = no_vig_probs({"home": h_o, "away": a_o, "draw": d_o})
        p = {
            match["home"]: probs.get("home", 0), 
            match["away"]: probs.get("away", 0), 
            "Remis": probs.get("draw", 0) * 0.9
        }

    min_odds = MIN_ODDS.get(match["league"], 2.5)
    best = None
    for sel, prob in p.items():
        odds = h_o if sel == match["home"] else a_o if sel == match["away"] else d_o
        if odds and odds >= min_odds:
            edge = prob - (1/odds)
            if edge >= VALUE_THRESHOLD:
                if not best or edge > best["val"]:
                    best = {"sel": sel, "odds": odds, "val": edge}
    return best

# ================= API FETCHING =================
def fetch_odds_safe(league, api_keys):
    """Pobiera kursy z obsługą błędów"""
    for key in api_keys:
        try:
            track_api_call(key)
            
            r = requests.get(
                f"https://api.the-odds-api.com/v4/sports/{league}/odds",
                params={"apiKey": key, "markets": "h2h", "regions": "eu"},
                timeout=10
            )
            
            if r.status_code == 401:
                logger.error(f"Błędny klucz API: {key[:8]}...")
                continue
            elif r.status_code == 429:
                logger.warning(f"Rate limit dla klucza: {key[:8]}...")
                continue
            elif r.status_code != 200:
                logger.error(f"Status {r.status_code} dla {league}")
                continue
            
            data = r.json()
            logger.info(f"Pobrano {len(data)} meczów dla {league}")
            return data
            
        except requests.Timeout:
            logger.error(f"Timeout dla {league} z kluczem {key[:8]}...")
        except requests.RequestException as e:
            logger.error(f"Request error dla {league}: {e}")
        except json.JSONDecodeError:
            logger.error(f"Błąd parsowania JSON dla {league}")
    
    logger.error(f"Nie udało się pobrać kursów dla {league}")
    return None

def fetch_scores_safe(league, api_keys):
    """Pobiera wyniki z obsługą błędów"""
    for key in api_keys:
        try:
            track_api_call(key)
            
            r = requests.get(
                f"https://api.the-odds-api.com/v4/sports/{league}/scores",
                params={"apiKey": key, "daysFrom": 3},
                timeout=10
            )
            
            if r.status_code == 200:
                data = r.json()
                logger.info(f"Pobrano {len(data)} wyników dla {league}")
                return data
            else:
                logger.warning(f"Status {r.status_code} dla wyników {league}")
                
        except Exception as e:
            logger.error(f"Błąd pobierania wyników {league}: {e}")
    
    return None

# ================= RESULTS =================
def check_results():
    logger.info("Sprawdzanie wyników...")
    coupons = load_json(COUPONS_FILE, [])
    bankroll = load_bankroll()
    results_found = 0
    
    for league in LEAGUES:
        data = fetch_scores_safe(league, API_KEYS)
        if not data:
            continue
        
        for c in coupons:
            if c["status"] != "pending" or c["league"] != league:
                continue
            
            m = next((x for x in data
                      if x["home_team"] == c["home"]
                      and x["away_team"] == c["away"]
                      and x.get("completed")), None)
            if not m:
                continue
            
            scores = {s["name"]: int(s["score"]) for s in m.get("scores", [])}
            hs, as_ = scores.get(c["home"], 0), scores.get(c["away"], 0)
            winner = c["home"] if hs > as_ else c["away"] if as_ > hs else "Remis"
            
            if winner == c["picked"]:
                profit = round(c["stake"] * (c["odds"] - 1), 2)
                bankroll += profit
                c["status"] = "won"
                c["win_val"] = profit
                icon = "✅"
                result_text = f"Wygrana: +{profit} PLN"
            else:
                c["status"] = "lost"
                c["win_val"] = 0
                icon = "❌"
                result_text = f"Przegrana: -{c['stake']} PLN"
            
            msg = (
                f"{icon} <b>ROZLICZENIE</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"<b>{c['home']} vs {c['away']}</b>\n"
                f"Wynik: <b>{hs}:{as_}</b>\n"
                f"Typ: <b>{c['picked']}</b> | Kurs: <b>{c['odds']}</b>\n"
                f"Stawka: <b>{c['stake']} PLN</b>\n"
                f"{result_text}"
            )
            send_msg(msg, target="results")
            results_found += 1
            logger.info(f"Rozliczono: {c['home']} vs {c['away']} - {c['status']}")
    
    save_bankroll(bankroll)
    save_json(COUPONS_FILE, coupons)
    logger.info(f"Rozliczono {results_found} zakładów")

# ================= STATS =================
def calculate_detailed_stats(coupons):
    """Oblicza szczegółowe statystyki"""
    value_coupons = [c for c in coupons if c.get("type") == "value"]
    
    if not value_coupons:
        return None
    
    stats = {
        "total_bets": len(value_coupons),
        "won": len([c for c in value_coupons if c["status"] == "won"]),
        "lost": len([c for c in value_coupons if c["status"] == "lost"]),
        "pending": len([c for c in value_coupons if c["status"] == "pending"]),
        "total_staked": sum(c.get("stake", 0) for c in value_coupons),
        "total_profit": sum(c.get("win_val", 0) for c in value_coupons),
        "total_loss": sum(c.get("stake", 0) for c in value_coupons if c["status"] == "lost"),
        "avg_odds": sum(c.get("odds", 0) for c in value_coupons) / len(value_coupons),
        "win_rate": 0,
        "roi": 0
    }
    
    completed = stats["won"] + stats["lost"]
    if completed > 0:
        stats["win_rate"] = (stats["won"] / completed) * 100
    
    if stats["total_staked"] > 0:
        net = stats["total_profit"] - stats["total_loss"]
        stats["roi"] = (net / stats["total_staked"]) * 100
    
    return stats

def send_stats():
    logger.info("Generowanie statystyk...")
    coupons = load_json(COUPONS_FILE, [])
    bankroll = load_bankroll()
    
    stats = calculate_detailed_stats(coupons)
    
    if not stats:
        send_msg("📊 Statystyki - Brak danych", target="results")
        return
    
    msg = (
        f"📊 <b>STATYSTYKI OGÓLNE</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💰 Bankroll: <b>{round(bankroll, 2)} PLN</b>\n"
        f"📈 ROI: <b>{round(stats['roi'], 2)}%</b>\n"
        f"🎯 Zakładów: <b>{stats['total_bets']}</b>\n"
        f"✅ Wygrane: <b>{stats['won']}</b> ({round(stats['win_rate'], 1)}%)\n"
        f"❌ Przegrane: <b>{stats['lost']}</b>\n"
        f"⏳ Oczekujące: <b>{stats['pending']}</b>\n"
        f"💵 Obrót: <b>{round(stats['total_staked'], 2)} PLN</b>\n"
        f"🟢 Zysk: <b>{round(stats['total_profit'], 2)} PLN</b>\n"
        f"🔴 Strata: <b>{round(stats['total_loss'], 2)} PLN</b>\n"
        f"📊 Średni kurs: <b>{round(stats['avg_odds'], 2)}</b>"
    )
    
    send_msg(msg, target="results")
    logger.info("Statystyki wysłane")
    
    # Statystyki per liga
    stats_by_league = defaultdict(lambda: {"types": 0, "won": 0, "lost": 0})
    for c in [c for c in coupons if c.get("type") == "value"]:
        stats_by_league[c["league"]]["types"] += 1
        if c["status"] == "won":
            stats_by_league[c["league"]]["won"] += c.get("win_val", 0)
        elif c["status"] == "lost":
            stats_by_league[c["league"]]["lost"] += c.get("stake", 0)
    
    if stats_by_league:
        league_msg = "📊 <b>STATYSTYKI PER LIGA</b>\n━━━━━━━━━━━━━━━━━━\n"
        for league, data in stats_by_league.items():
            profit = data["won"] - data["lost"]
            info = LEAGUE_INFO.get(league, {"name": league, "flag": "🎯"})
            league_msg += (
                f"{info['flag']} <b>{info['name']}</b>\n"
                f"Typów: {data['types']} | "
                f"Zysk: {round(profit, 2)} PLN\n"
            )
        send_msg(league_msg, target="results")

# ================= RUN =================
def run():
    logger.info("========== START SKANOWANIA ==========")
    backup_data()
    
    check_results()
    
    coupons = load_json(COUPONS_FILE, [])
    bankroll = load_bankroll()
    
    logger.info(f"Bankroll: {bankroll} PLN")
    
    # Sprawdź limity
    if not check_limits(coupons, bankroll):
        logger.warning("Zatrzymano z powodu limitów")
        return
    
    now = datetime.now(timezone.utc)
    all_picks = []
    
    for league in LEAGUES:
        logger.info(f"Skanowanie: {league}")
        data = fetch_odds_safe(league, API_KEYS)
        
        if not data:
            continue
        
        for e in data:
            try:
                dt = parser.isoparse(e["commence_time"])
                if not (now <= dt <= now + timedelta(hours=MAX_HOURS_AHEAD)):
                    continue
                
                odds = {}
                for bm in e["bookmakers"]:
                    for m in bm["markets"]:
                        if m["key"] == "h2h":
                            for o in m["outcomes"]:
                                odds[o["name"]] = max(odds.get(o["name"], 0), o["price"])
                
                odds_data = {
                    "home": odds.get(e["home_team"]),
                    "away": odds.get(e["away_team"]),
                    "draw": odds.get("Draw")
                }
                
                if not validate_odds(odds_data, league):
                    continue
                
                pick = generate_pick({
                    "home": e["home_team"],
                    "away": e["away_team"],
                    "league": league,
                    "odds": odds_data
                })
                
                if pick:
                    all_picks.append((pick, e, dt, league))
                    logger.info(f"Value bet: {e['home_team']} vs {e['away_team']} - Edge: {pick['val']*100:.2f}%")
            
            except Exception as ex:
                logger.error(f"Błąd przetwarzania meczu {e.get('home_team', 'UNKNOWN')}: {ex}")
    
    logger.info(f"Znaleziono {len(all_picks)} value betów")
    
    bets_placed = 0
    for pick, e, dt, league in sorted(all_picks, key=lambda x: x[0]["val"], reverse=True):
        if not check_limits(coupons, bankroll):
            logger.info("Limit zakładów osiągnięty, przerywam")
            break
        
        stake = calc_kelly_stake(bankroll, pick["odds"], pick["val"])
        if stake <= 0:
            continue
        
        bankroll -= stake
        save_bankroll(bankroll)
        
        coupon = {
            "home": e["home_team"],
            "away": e["away_team"],
            "picked": pick["sel"],
            "odds": pick["odds"],
            "stake": stake,
            "league": league,
            "status": "pending",
            "win_val": 0,
            "sent_date": str(now.date()),
            "type": "value",
            "edge": round(pick["val"] * 100, 2)
        }
        
        coupons.append(coupon)
        send_msg(format_value_card(league, e["home_team"], e["away_team"], dt, pick["sel"], pick["odds"], pick["val"], stake))
        
        bets_placed += 1
        logger.info(f"Obstawiono: {e['home_team']} vs {e['away_team']} | Stawka: {stake} PLN")
    
    save_json(COUPONS_FILE, coupons)
    logger.info(f"========== KONIEC - Obstawiono {bets_placed} zakładów ==========")

# ================= MAIN =================
if __name__ == "__main__":
    try:
        if "--stats" in sys.argv:
            send_stats()
        else:
            run()
    except Exception as e:
        logger.critical(f"KRYTYCZNY BŁĄD: {e}", exc_info=True)
        send_msg(f"🚨 <b>BŁĄD KRYTYCZNY</b>\n{str(e)}", target="results")
