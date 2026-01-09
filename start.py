def run():
    check_results()  # najpierw rozliczamy poprzednie kupony
    coupons = load_json(COUPONS_FILE, [])
    bankroll = load_bankroll()
    now = datetime.now(timezone.utc)
    all_picks = []

    # --- Pobranie wszystkich meczy ---
    for league in LEAGUES:
        for key in API_KEYS:
            try:
                r = requests.get(
                    f"https://api.the-odds-api.com/v4/sports/{league}/odds",
                    params={"apiKey": key, "markets": "h2h", "regions": "eu"},
                    timeout=10
                )
                if r.status_code != 200:
                    continue

                for e in r.json():
                    dt = parser.isoparse(e["commence_time"])
                    if not (now <= dt <= now + timedelta(hours=MAX_HOURS_AHEAD)):
                        continue

                    odds = {}
                    for bm in e["bookmakers"]:
                        for m in bm["markets"]:
                            if m["key"] == "h2h":
                                for o in m["outcomes"]:
                                    odds[o["name"]] = max(odds.get(o["name"], 0), o["price"])

                    # --- VALUE pick ---
                    value_pick = generate_pick({
                        "home": e["home_team"],
                        "away": e["away_team"],
                        "league": league,
                        "odds": {
                            "home": odds.get(e["home_team"]),
                            "away": odds.get(e["away_team"]),
                            "draw": odds.get("Draw")
                        }
                    })

                    # --- BTTS/Over placeholder (jeśli masz własną logikę) ---
                    btts_over_pick = generate_btts_over_pick(e, league, odds)  # zdefiniuj tę funkcję

                    # --- Sprawdzenie duplikatów ---
                    if not any(c for c in coupons if c["home"] == e["home_team"] and c["away"] == e["away_team"] and c["sent_date"] == str(now.date())):
                        all_picks.append({
                            "league": league,
                            "match": e,
                            "dt": dt,
                            "value": value_pick,
                            "btts_over": btts_over_pick
                        })
                break
            except Exception as ex:
                print(f"DEBUG: Błąd pobierania meczów {league}: {ex}")
                continue

    # --- Podział na VALUE i BTTS/Over ---
    value_matches = [m for m in all_picks if m["value"]]
    btts_over_matches = [m for m in all_picks if m["btts_over"]]

    # --- Wysyłka VALUE ---
    for m in value_matches:
        pick = m["value"]
        stake = calc_kelly_stake(bankroll, pick["odds"], pick["val"])
        if stake <= 0:
            continue
        bankroll -= stake
        save_bankroll(bankroll)

        coupons.append({
            "home": m["match"]["home_team"],
            "away": m["match"]["away_team"],
            "picked": pick["sel"],
            "odds": pick["odds"],
            "stake": stake,
            "league": m["league"],
            "status": "pending",
            "win_val": 0,
            "sent_date": str(now.date()),
            "type": "value"
        })

        print(f"DEBUG: Wysyłam VALUE na Telegram: {m['match']['home_team']} vs {m['match']['away_team']}")
        send_msg(format_value_card(m["league"], m["match"]["home_team"], m["match"]["away_team"], m["dt"], pick["sel"], pick["odds"], pick["val"], stake))

    # --- Wysyłka BTTS/Over ---
    for m in btts_over_matches:
        pick = m["btts_over"]
        stake = calc_kelly_stake(bankroll, pick["odds"], pick["val"])
        if stake <= 0:
            continue
        bankroll -= stake
        save_bankroll(bankroll)

        coupons.append({
            "home": m["match"]["home_team"],
            "away": m["match"]["away_team"],
            "picked": pick["sel"],
            "odds": pick["odds"],
            "stake": stake,
            "league": m["league"],
            "status": "pending",
            "win_val": 0,
            "sent_date": str(now.date()),
            "type": "btts_over"
        })

        print(f"DEBUG: Wysyłam BTTS/Over na Telegram: {m['match']['home_team']} vs {m['match']['away_team']}")
        send_msg(format_value_card(m["league"], m["match"]["home_team"], m["match"]["away_team"], m["dt"], pick["sel"], pick["odds"], pick["val"], stake))

    save_json(COUPONS_FILE, coupons)