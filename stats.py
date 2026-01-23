    for bet in history:
        # Całkowicie pomijamy remisy
        if bet.get('outcome') == 'Draw':
            continue

        valid_bets_count += 1
        profit = bet.get('profit', 0)
        total_net_profit += profit
        total_turnover += bet.get('stake', 250)
        
        if bet.get('status') == 'WIN':
            total_wins += 1

        # --- LOGIKA IKON SPORTOWYCH ---
        sport_raw = bet.get('sport', '').lower()
        if "icehockey" in sport_raw:
            s_icon = "🏒"
        elif "soccer" in sport_raw:
            s_icon = "⚽"
        elif "basketball" in sport_raw:
            s_icon = "🏀"
        elif "tennis" in sport_raw:
            s_icon = "🎾"
        else:
            s_icon = "🔹"

        # Czyszczenie nazwy ligi
        l_name = sport_raw.replace('soccer_', '').replace('icehockey_', '').replace('basketball_', '').replace('tennis_', '').replace('_', ' ').upper()
        
        # Dobieranie flagi państwa
        flag = "🏳️"
        for country, f_emoji in FLAG_MAP.items():
            if country in l_name:
                flag = f_emoji
                break
        
        # Łączymy wszystko w jeden czytelny wiersz
        full_league_display = f"{s_icon} {flag} {l_name}"
        
        if full_league_display not in league_stats:
            league_stats[full_league_display] = {'profit': 0.0, 'bets': 0}
        league_stats[full_league_display]['profit'] += profit
        league_stats[full_league_display]['bets'] += 1
