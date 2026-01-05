# ================= KONFIGURACJA =================
# ... (reszta zmiennych bez zmian)
MAX_ODDS = 3.20      # NOWY LIMIT: Maksymalny kurs 3.20
# ...

def find_new_bets():
    coupons = load_data(COUPONS_FILE)
    sent_today = [c.get("event_id") for c in coupons]
    potential_bets = []
    now = datetime.now(timezone.utc)
    horizon = now + timedelta(hours=48)

    for sport_key, league_label in SPORTS.items():
        for key in API_KEYS:
            try:
                r = requests.get(f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/", 
                               params={"apiKey": key, "regions": "eu", "markets": "h2h"}, timeout=15)
                if r.status_code != 200: continue
                events = r.json()
                for ev in events:
                    if ev['id'] in sent_today: continue
                    commence_time = datetime.fromisoformat(ev['commence_time'].replace('Z', '+00:00'))
                    if commence_time > horizon: continue
                    
                    outcomes_prices = {}
                    for b in ev.get("bookmakers", []):
                        for m in b['markets']:
                            for out in m['outcomes']:
                                if out['name'] not in outcomes_prices: outcomes_prices[out['name']] = []
                                outcomes_prices[out['name']].append(out['price'])
                    
                    best_option = None
                    for bookie in ev.get("bookmakers", []):
                        if bookie['key'] in ['betfair_ex', 'pinnacle']: continue
                        for m in bookie['markets']:
                            for out in m['outcomes']:
                                local_p, avg_p = out['price'], sum(outcomes_prices[out['name']])/len(outcomes_prices[out['name']])
                                
                                # ZASTOSOWANIE LIMITU 3.20
                                if (local_p * TAX_RATE) > (avg_p * VALUE_MIN) and local_p <= MAX_ODDS:
                                    profit = round(((local_p * TAX_RATE) / avg_p - 1) * 100, 1)
                                    if not best_option or profit > best_option['val']:
                                        best_option = {"val": profit, "p": local_p, "avg": avg_p, "name": out['name'], "ev": ev, "sport": sport_key}
                    if best_option: potential_bets.append(best_option)
                break 
            except: continue
    
    # ... (kod wysyłający wiadomości bez zmian)
