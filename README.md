# 📈 Betting Bot Professional v2.0

Automatyczny system skanowania i rozliczania typów sportowych oparty na **The Odds API** oraz **GitHub Actions**.

## 🚀 Główne Funkcje
* **Multi-Key System:** Obsługa 5 kluczy API (2500 zapytań/miesiąc).
* **Smart Scanning:** Skanowanie 7 topowych lig świata 4 razy dziennie.
* **Auto-Settler:** Automatyczne rozliczanie wyników o 22:00.
* **Inteligentne Statystyki:** Analiza skuteczności wg lig, kursów i dni tygodnia.
* **Miesięczne Archiwum:** Automatyczne zamrażanie wyników w plikach historycznych.

## ⚙️ Strategia
* **Bankroll początkowy:** 1000 PLN (domyślnie).
* **Stawka:** Stałe 2% aktualnego budżetu.
* **Zakres kursów:** 1.50 - 2.50.
* **Czas:** Skanowanie meczów do 48h przed startem.

## 📊 Monitorowane Ligi
| Dyscyplina | Liga | Emoji |
| :--- | :--- | :--- |
| Piłka Nożna | EPL, La Liga, Bundesliga, Serie A, Ligue 1 | ⚽ |
| Koszykówka | NBA | 🏀 |
| Hokej | NHL | 🏒 |

## 🛠 Konfiguracja Secrets (GitHub)
Aby bot działał, w ustawieniach repozytorium (`Settings > Secrets and variables > Actions`) muszą znajdować się:
* `T_TOKEN`: Token bota Telegram.
* `T_CHAT`: ID czatu dla nowych ofert.
* `T_CHAT_RESULTS`: ID czatu dla raportów (może być to samo).
* `ODDS_KEY` do `ODDS_KEY_5`: Klucze z the-odds-api.com.

## 📁 Struktura Plików
* `start.py` - Skaner ofert.
* `settle.py` - Rozliczanie zakończonych meczów.
* `stats.py` - Generator raportów i analityka.
* `coupons.json` - Aktywne zakłady.
* `history.json` - Wyniki z bieżącego miesiąca.
* `bankroll.json` - Aktualny stan konta.

---
*System uruchamia się automatycznie przez GitHub Actions. Ostatnia aktualizacja strategii: 16.01.2026*
