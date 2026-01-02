import requests
import os
import json
from datetime import datetime, timedelta, timezone

# ================= KONFIGURACJA =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")
KEYS_POOL = [os.getenv(f"ODDS_KEY{i}") for i in ["", "_2", "_3", "_4", "_5"]]
API_KEYS = [k for k in KEYS_POOL if k]

# PROGI KURSOWE
MIN_SINGLE_ODD = 1.35
MAX_SINGLE_ODD = 1.95
SINGLE_THRESHOLD = 2.05  
TAX_RATE = 0.88

STAKE_STANDARD = 50.0    
STAKE_SINGLE = 80.0      

# FILTRY
MAX_VARIANCE = 0.12
MIN_BOOKMAKERS = 4

SPORTS_CONFIG = {
    "soccer_epl": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League", 
    "soccer_spain_la_liga": "🇪🇸 La Liga",
    "soccer_germany_bundesliga": "🇩🇪 Bundesliga", 
    "soccer_italy_serie_a": "🇮🇹 Serie A",
    "soccer_france_ligue_one": "🇫🇷 Ligue 1", 
    "soccer_poland_ekstraklasa": "🇵🇱 Ekstraklasa",
    "soccer_netherlands_ere_divisie": "🇳🇱 Eredivisie",
    "soccer_portugal_primeira_liga": "🇵🇹 Primeira Liga",
    "soccer_uefa_champions_league": "🇪🇺 Liga Mistrzów", 
    "soccer_uefa_europa_league": "🇪🇺 Liga Europy",
    "basketball_nba": "🏀 NBA"
}

COUPONS_FILE = "coupons.json"

# ================= FUNKCJE POMOCNICZE =================

def load_coupons():
    if not os.path.exists(COUPONS_FILE): return []
    try:
        with open(COUPONS_FILE, "r") as f: return json.load(f)
    except: return []

def save_coupons(coupons):
    with open(COUPONS_FILE, "w") as f: 
        json.dump(coupons[-500:], f, indent=4)

def send_msg(text):
    if not T_TOKEN or not T_CHAT: return
    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
    try: 
        requests.post(url, json={"chat_id": T_CHAT, "text": text, "parse_mode": "Markdown"}, timeout=15)
    except: 
        pass

# ================= RAPORTOWANIE =================

def send_daily_report():
    coupons = load_coupons()
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)
    
    # Filtrujemy tylko rozliczone kupony z ostatnich 24h
    completed_today = [c for c in coupons if c.get("status") in ["win", "loss"] 
                       and "end_time" in c 
                       and datetime.fromisoformat(c["end_time"]) > yesterday]
    
    if not completed_today:
        send_msg("📊 *RAPORT DZIENNY*\n━━━━━━━━━━━━━━━\nW ciągu ostatnich 24h nie rozliczono żadnych nowych kuponów.")
        return

    total_stake = sum(c["stake"] for c in completed_today)
    total_win = sum(c["win_val"] if c["status"] == "win" else 0 for c in completed_today)
    profit = total_win - total_stake
    wins = len([c for c in completed_today if c["status"] == "win"])
    total = len(completed_today)
    accuracy = (wins / total) * 100 if total > 0 else 0

    icon = "📈" if profit >= 0 else "📉"
    
    report = (
        f"📊 *RAPORT DZIENNY (24h)*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ Rozliczone kupony: `{total}`\n"
        f"🎯 Skuteczność: `{accuracy:.1f}%` ({wins}/{total})\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Zainwestowano: `{total_stake:.2f} PLN`\n"
        f"💰 Zwrot: `{total_win:.2f} PLN`\n"
        f"{icon} **Bilans:** `{profit:+.2f} PLN`"
    )
    send_msg(report)

# ================= LOGIKA ROZLICZANIA =================

def check_results():
    coupons = load_coupons()
    updated = False
    now = datetime.now(timezone.utc)
    
    for c in coupons:
        if c.get("status") != "pending": continue
        
        end_time = datetime.fromisoformat(c["end_time"])
        if now < end_time + timedelta(hours=4): continue

        matches_results = []
        for m_saved in c["matches"]:
            s_key = m_saved.get("sport_key")
            if not s_key: continue

            for key in API_KEYS:
                try:
                    r = requests.get(f"https://api.the-odds-api.com/v4/sports/{s_key}/scores/", 
                                   params={"apiKey": key, "daysFrom": 3}, timeout=15)
                    if r.status_code == 200:
                        scores = r.json()
                        s_data = next((s for s in scores if s["id"] == m_saved["id"] and s
