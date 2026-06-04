# Morning Stock Scanner Pipeline

A fully automated, self-contained Python pipeline that scans all S&P 500 tickers each morning, applies multi-stage filtering (sentiment → geopolitical → technical → stress-test), and generates a dated Markdown report by 08:45 AM UK time.

## Pipeline Stages

| Stage | Filter | Input → Output |
|-------|--------|----------------|
| 1 | **Sentiment** – VADER scores on last-24h headlines | 500 → 15 |
| 2 | **Geopolitical** – keyword risk matrix (tariffs, oil, escalation…) | 15 → 10 |
| 3 | **Technical** – RSI, pre-market volume, price velocity via Polygon | 10 → 5 |
| 4 | **Stress-Test** – resistance proximity, volume dry-up, data gaps | 5 → 2 |

## Quick Start

```bash
# 1. Clone & enter
git clone https://github.com/amitahlawatox/morning-stock-scanner.git
cd morning-stock-scanner

# 2. Create virtual environment & install
python3 -m venv scanner/.venv
source scanner/.venv/bin/activate
pip install -r scanner/requirements.txt

# 3. Configure API keys
cp .env.example .env
# Edit .env with your Finnhub + Polygon keys

# 4. Run the scanner
python -m scanner.main

# 5. Dry-run (test symbol ingestion only)
python -m scanner.main --dry
```

## API Keys Required

| Service | Free Tier | Rate Limit | Get Key |
|---------|-----------|------------|---------|
| **Finnhub** | Yes | 60 calls/min | [finnhub.io/register](https://finnhub.io/register) |
| **Polygon.io** | Yes | 5 calls/min | [polygon.io/dashboard/signup](https://polygon.io/dashboard/signup) |

## Cron Schedule (Mon–Fri 08:00 UK)

```bash
# Show the crontab line
python -m scanner.scheduler --show

# Auto-install to crontab
python -m scanner.scheduler --install
```

The cron uses `CRON_TZ=Europe/London` to handle GMT ↔ BST automatically.

## Output

Reports are saved to `reports/YYYY-MM-DD_intraday_report.md` with:
- Dominant morning geopolitical themes
- Final 2 selected tickers
- Per-ticker data: sentiment score, best headline, pre-market entry level, RSI, stress-test results

## Project Structure

```
scanner/
├── __init__.py
├── config.py            # Central configuration & thresholds
├── symbols.py           # S&P 500 ticker ingestion from Wikipedia
├── data_acquisition.py  # Finnhub news fetching (general + per-ticker)
├── sentiment.py         # Stage 1: VADER sentiment filter
├── geopolitical.py      # Stage 2: Geopolitical risk cross-reference
├── technicals.py        # Stage 3: Polygon pre-market technicals
├── stress_test.py       # Stage 4: Devil's advocate stress-test
├── report.py            # Markdown report generator
├── scheduler.py         # Cron installer & display
├── main.py              # Pipeline orchestrator
└── requirements.txt     # Python dependencies
reports/                 # Auto-generated daily reports
.env.example             # Template for API keys
```

## Disclaimer

This tool is for educational and informational purposes only. It is **not financial advice**. Always perform your own due diligence before making investment decisions.
