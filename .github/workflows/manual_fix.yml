name: Fix History Results
on: workflow_dispatch # Pozwala na ręczne uruchomienie przyciskiem

jobs:
  fix:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'

      - name: Install dependencies
        run: pip install requests

      - name: Run Fix Script
        env:
          ODDS_KEY: ${{ secrets.ODDS_KEY }} # Musisz mieć klucze w Secrets
          ODDS_KEY_2: ${{ secrets.ODDS_KEY_2 }}
        run: python fix_history.py

      - name: Commit changes
        run: |
          git config --global user.name "GitHub Action"
          git config --global user.email "action@github.com"
          git add history.json
          git commit -m "Fix: Uzupełnienie brakujących wyników" || echo "No changes to commit"
          git push
