import os
import requests
import json
import time
from datetime import datetime, timedelta, timezone
from stats import generate_stats  # IMPORT TWOJEJ FUNKCJI

# ================= KONFIGURACJA LIG =================
SPORTS_CONFIG = {
    # ... (zostawiam Twoją listę SPORTS_CONFIG bez zmian)
    "icehockey_nhl": "🏒", 
    "icehockey_sweden_allsvenskan": "🇸🇪",
    "icehockey_sweden_svenska_rinkbandy": "🇸🇪",
    "icehockey_finland_liiga": "🇫🇮",
    "icehockey_germany_del": "🇩🇪",
    "icehockey_czech_extraliga": "🇨🇿",
    "icehockey_switzerland_nla": "🇨🇭",
    "icehockey_austria_liga": "🇦🇹",
    "icehockey_denmark_metal_ligaen": "🇩🇰",
    "icehockey_norway_eliteserien": "🇳🇴",
    "icehockey_slovakia_extraliga": "🇸🇰",
    "soccer_epl": "⚽",
    "soccer_germany_bundesliga": "🇩🇪",
    "soccer_italy_serie_a": "🇮🇹", 
    "soccer_spain_la_liga": "🇪🇸",
    "soccer_poland_ekstraklasa": "🇵🇱",
    "soccer_france_ligue_one": "🇫🇷",
    "soccer_portugal_primeira_liga": "🇵🇹",
    "soccer_netherlands_erevidisie": "🇳🇱",
    "soccer_turkey_super_lig": "🇹🇷",
    "soccer_belgium_first_division_a": "🇧🇪",
    "soccer_austria_bundesliga": "🇦🇹",
    "soccer_denmark_superliga": "🇩🇰",
    "soccer_greece_super_league": "🇬🇷",
    "soccer_switzerland_superleague": "🇨🇭",
    "soccer_scotland_premier_league": "🏴󠁧󠁢󠁳󠁣󠁴󠁿",
    "soccer_efl_championship": "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
    "basketball_euroleague": "🏀",
    "tennis_atp_australian_open": "🎾",
    "tennis_wta_australian_open": "🎾"
}

# ================= KONFIGURACJA =================
API_KEYS = []
if os.getenv("ODDS_KEY"): API_KEYS.append(os.getenv("ODDS_KEY"))
for i in range(2, 11):
    key = os.getenv(f"ODDS_KEY_{i}")
    if key and len(key) > 10: API_KEYS.append(key)

TELEGRAM_TOKEN = os.getenv("T_TOKEN")
TELEGRAM_CHAT = os.getenv("T_CHAT")
HISTORY_FILE = "history.json"
COUPONS_FILE = "coupons.json"
KEY_STATE_FILE = "key_index.txt"
BASE_STAKE = 350

# ... (funkcje get_current_key_idx, save_current_key_idx, get_smart_stake zostają bez zmian)

def send_telegram(message, mode="HTML"): # DODANO OBSŁUGĘ TRYBU
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try: 
        requests.post(url, json={
            "chat_id": TELEGRAM_CHAT, 
            "text": message, 
            "parse_mode": mode # Zmieniono na zmienny tryb
        })
    except: pass

# ... (funkcja load_existing_data zostaje bez zmian)

def main():
    print(f"🚀 START BOT PRO: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if not API_KEYS:
        print("❌ Błąd: Brak kluczy API!")
        return

    current_key_idx = get_current_key_idx()
    all_coupons = load_existing_data()
    already_sent_ids = [c['id'] for c in all_coupons]
    now = datetime.now(timezone.utc)
    max_future = now + timedelta(hours=48)

    # --- KROK 1: SKANOWANIE I WYSYŁANIE TYPÓW ---
    for league, flag_emoji in SPORTS_CONFIG.items():
        current_stake, base_threshold = get_smart_stake(league)
        print(f"📡 SKANOWANIE: {league.upper()} (Stawka: {current_stake} PLN)")
        
        # ... (cała Twoja pętla skanowania, pobierania danych i wysyłania typów zostaje bez zmian)
        # Tutaj wykonuje się Twój oryginalny kod...
        # [Pomiędzy kodem skanowania a save_current_key_idx]

    # --- KROK 2: ZAPIS DANYCH ---
    save_current_key_idx(current_key_idx)
    with open(COUPONS_FILE, "w", encoding="utf-8") as f:
        json.dump(all_coupons, f, indent=4)
    print(f"✅ KONIEC SKANOWANIA. Aktywne kupony: {len(all_coupons)}")

    # --- KROK 3: GENEROWANIE I WYSYŁKA STATYSTYK NA TELEGRAM ---
    print("📊 GENEROWANIE STATYSTYK...")
    try:
        raport_stats = generate_stats()
        send_telegram(raport_stats, mode="Markdown") # WYSYŁKA W TRYBIE MARKDOWN
        print("✅ STATYSTYKI WYSŁANE NA TELEGRAM")
    except Exception as e:
        print(f"❌ BŁĄD STATYSTYK: {e}")

if __name__ == "__main__":
    main()
