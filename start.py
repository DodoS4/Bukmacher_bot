# --- ZMIENIONE PARAMETRY W KONFIGURACJI ---
MIN_BOOKMAKERS = 7  # Opcja 4: Większa płynność (minimum 7 bukmacherów)

def run():
    now = datetime.now(timezone.utc)
    sent_ids = load_data()
    
    # Słownik do grupowania meczów według lig (Opcja 3)
    leagues_pools = {} 

    for sport_key, sport_label in SPORTS_CONFIG.items():
        matches = None
        for key in API_KEYS:
            try:
                r = requests.get(
                    f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/",
                    params={"apiKey": key, "regions": "eu", "markets": "h2h"},
                    timeout=15
                )
                if r.status_code == 200:
                    matches = r.json()
                    break
            except: continue

        if not matches: continue

        for m in matches:
            m_id = m["id"]
            if m_id in sent_ids: continue
            
            # --- FILTR OPCJA 4: LICZBA BUKMACHERÓW ---
            if len(m.get("bookmakers", [])) < MIN_BOOKMAKERS:
                continue

            m_dt_utc = datetime.fromisoformat(m["commence_time"].replace('Z', '+00:00'))
            m_dt_pl = m_dt_utc + timedelta(hours=1) # Sugestia: użyj ZoneInfo dla idealnego czasu
            
            if m_dt_utc < now or m_dt_utc > (now + timedelta(hours=48)): continue

            home, away = m["home_team"], m["away_team"]
            h_odds, a_odds = [], []

            for bm in m.get("bookmakers", []):
                for market in bm.get("markets", []):
                    if market["key"] == "h2h":
                        for o in market["outcomes"]:
                            if o["name"] == home: h_odds.append(o["price"])
                            if o["name"] == away: a_odds.append(o["price"])

            # Ponowna weryfikacja liczby kursów po przefiltrowaniu rynku h2h
            if len(h_odds) < MIN_BOOKMAKERS: continue
                
            avg_h, min_h, max_h = sum(h_odds)/len(h_odds), min(h_odds), max(h_odds)
            avg_a, min_a, max_a = sum(a_odds)/len(a_odds), min(a_odds), max(a_odds)

            var_h = (max_h - min_h) / avg_h
            var_a = (max_a - min_a) / avg_a

            pick = None
            if MIN_SINGLE_ODD <= avg_h <= MAX_SINGLE_ODD and var_h <= MAX_VARIANCE:
                pick = {"id": m_id, "team": home, "odd": avg_h, "league": sport_label, "vs": away, "golden": avg_h <= GOLDEN_MAX_ODD, "dropping": (avg_h - min_h) > 0.05, "date": m_dt_pl.strftime("%d.%m %H:%M")}
            elif MIN_SINGLE_ODD <= avg_a <= MAX_SINGLE_ODD and var_a <= MAX_VARIANCE:
                pick = {"id": m_id, "team": away, "odd": avg_a, "league": sport_label, "vs": home, "golden": avg_a <= GOLDEN_MAX_ODD, "dropping": (avg_a - min_a) > 0.05, "date": m_dt_pl.strftime("%d.%m %H:%M")}

            if pick:
                if sport_label not in leagues_pools:
                    leagues_pools[sport_label] = []
                leagues_pools[sport_label].append(pick)

    # --- OPCJA 3: INTELIGENTNE PAROWANIE MIĘDZY LIGAMI ---
    final_coupons = []
    
    # Wyciągamy wszystkie typy do jednej listy, ale zachowujemy informację o lidze
    all_picks = []
    for league_name in leagues_pools:
        # Sortujemy mecze wewnątrz ligi od najlepszych (golden)
        leagues_pools[league_name].sort(key=lambda x: (x['golden'], x['dropping']), reverse=True)
        all_picks.extend(leagues_pools[league_name])

    # Sortujemy globalnie, by najpierw parować najlepsze okazje
    all_picks.sort(key=lambda x: (x['golden'], x['dropping']), reverse=True)

    while len(all_picks) >= 2:
        p1 = all_picks.pop(0) # Bierzemy najlepszy dostępny mecz
        
        # Szukamy drugiego meczu, który NIE jest z tej samej ligi
        p2_index = -1
        for i in range(len(all_picks)):
            if all_picks[i]['league'] != p1['league']:
                p2_index = i
                break
        
        if p2_index != -1:
            p2 = all_picks.pop(p2_index)
            # Tutaj następuje wysyłka wiadomości (Twój msg logic)
            generate_and_send_coupon(p1, p2, sent_ids)
        else:
            # Jeśli zostały mecze tylko z jednej ligi, nie parujemy ich (dywersyfikacja)
            break

    save_data(sent_ids)

def generate_and_send_coupon(p1, p2, sent_ids):
    # Tutaj wstaw swoją logikę formatowania wiadomości (f"🌟 **ZŁOTY DOUBLE**...")
    # oraz wywołanie send_msg(msg)
    # Na końcu:
    sent_ids.extend([p1['id'], p2['id']])
