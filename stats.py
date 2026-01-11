name: Betting Bot 24/7

on:
  schedule:
    - cron: '0 6,12,18,22 * * *' # Skanowanie 4 razy dziennie
  workflow_dispatch: # Pozwala na ręczne uruchomienie

jobs:
  run-bot:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install requests python-dateutil

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

      - name: Run Settler (settle.py)
        env:
          T_TOKEN: ${{ secrets.T_TOKEN }}
          T_CHAT_RESULTS: ${{ secrets.T_CHAT_RESULTS }}
          ODDS_KEY: ${{ secrets.ODDS_KEY }}
        run: python settle.py

      - name: Run Stats (stats.py)
        env:
          T_TOKEN: ${{ secrets.T_TOKEN }}
          T_CHAT_RESULTS: ${{ secrets.T_CHAT_RESULTS }}
        run: python stats.py

      - name: Commit and push changes
        run: |
          git config --global user.name "github-actions[bot]"
          git config --global user.email "github-actions[bot]@users.noreply.github.com"
          git add coupons.json
          git commit -m "Update coupons and stats [skip ci]" || exit 0
          git push
