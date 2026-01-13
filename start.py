name: Betting Bot 24/7

on:
  schedule:
    # Skan + settle + stats (kilka razy dziennie)
    - cron: '0 6,12,18,22 * * *'

    # Tygodniowy raport + ranking lig (niedziela 22:00)
    - cron: '0 22 * * 0'

  workflow_dispatch:

jobs:
  run-bot:
    runs-on: ubuntu-latest

    steps:
      # ================= CHECKOUT =================
      - name: Checkout repository
        uses: actions/checkout@v3
        with:
          fetch-depth: 0   # WAŻNE – potrzebne do rebase

      # ================= PYTHON =================
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install requests python-dateutil

      # ================= SCANNER =================
      - name: Run Scanner (start.py)
        env:
          T_TOKEN: ${{ secrets.T_TOKEN }}
          T_CHAT: ${{ secrets.T_CHAT }}
          ODDS_KEY: ${{ secrets.ODDS_KEY }}
          ODDS_KEY_2: ${{ secrets.ODDS_KEY_2 }}
          ODDS_KEY_3: ${{ secrets.ODDS_KEY_3 }}
          ODDS_KEY_4: ${{ secrets.ODDS_KEY_4 }}
          ODDS_KEY_5: ${{ secrets.ODDS_KEY_5 }}
        run: python start.py

      # ================= SETTLER =================
      - name: Run Settler (settle.py)
        env:
          T_TOKEN: ${{ secrets.T_TOKEN }}
          T_CHAT_RESULTS: ${{ secrets.T_CHAT_RESULTS }}
          ODDS_KEY: ${{ secrets.ODDS_KEY }}
          ODDS_KEY_2: ${{ secrets.ODDS_KEY_2 }}
          ODDS_KEY_3: ${{ secrets.ODDS_KEY_3 }}
          ODDS_KEY_4: ${{ secrets.ODDS_KEY_4 }}
          ODDS_KEY_5: ${{ secrets.ODDS_KEY_5 }}
        run: python settle.py

      # ================= STATS / WEEKLY =================
      - name: Run Stats (weekly report + ranking)
        env:
          T_TOKEN: ${{ secrets.T_TOKEN }}
          T_CHAT_RESULTS: ${{ secrets.T_CHAT_RESULTS }}
        run: python stats.py

      # ================= SAVE DATA =================
      - name: Commit and push data safely
        run: |
          git config --global user.name "github-actions[bot]"
          git config --global user.email "github-actions[bot]@users.noreply.github.com"

          git add coupons_notax.json
          git commit -m "Update coupons & stats [skip ci]" || echo "Nothing to commit"

          # POBIERZ ZMIANY Z GITHUBA (rozwiązuje konflikty)
          git pull --rebase origin main || true

          # WYPCHNIJ DANE
          git push origin main