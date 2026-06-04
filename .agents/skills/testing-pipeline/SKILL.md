---
name: testing-morning-stock-scanner
description: End-to-end test procedure for the morning stock scanner pipeline. Use when verifying pipeline functionality after code changes.
---

# Testing the Morning Stock Scanner Pipeline

## Overview

This is a CLI-only Python pipeline. All testing is via shell commands — no browser/GUI interaction needed, so no screen recording is required.

The full pipeline takes **~12-13 minutes** due to API rate limits:
- Finnhub: 500 tickers × 1.1s delay = ~9-10 min
- Polygon: 10 tickers × 12s delay = ~2 min

## Devin Secrets Needed

- `FINNHUB_API_KEY` — Free tier API key from https://finnhub.io/
- `POLYGON_API_KEY` — Free tier API key from https://polygon.io/

These should be in `.env` at the repo root.

## Environment Setup

```bash
cd /home/ubuntu/repos/morning-stock-scanner
python3 -m venv scanner/.venv
source scanner/.venv/bin/activate
pip install -r scanner/requirements.txt
```

Verify API keys are loaded:
```bash
python -c "from scanner.config import FINNHUB_API_KEY, POLYGON_API_KEY; print('Finnhub:', bool(FINNHUB_API_KEY), 'Polygon:', bool(POLYGON_API_KEY))"
```

## Quick Smoke Test (5 seconds)

```bash
python -m scanner.main --dry
```

Expected: Loads 500+ tickers, prints `[DRY RUN] Exiting after symbol ingestion.`, exit code 0.

## Full Pipeline Test (~12 min)

```bash
python -m scanner.main 2>&1 | tee /tmp/full_run_output.txt
```

### Pass Criteria Per Stage

| Stage | Expected Output | Pass If |
|-------|----------------|--------|
| Step 1: Symbols | `→ XXX tickers loaded` | XXX ≥ 400 |
| Step 2: News | `→ N macro headlines` + `M tickers had news` | N > 0, M > 0 |
| Step 3: Sentiment | `→ N tickers passed` | 1 ≤ N ≤ 15 |
| Step 4: Geopolitical | `→ N tickers survived` | N ≤ 10 |
| Step 5: Technical | `→ N tickers shortlisted` | N ≤ 5, no crash |
| Step 6: Stress-Test | `→ N tickers survived` | N ≤ 2 |
| Step 7: Report | `→ Report saved: ...` | File exists on disk |
| Completion | `PIPELINE COMPLETE` | Exit code 0 |

### Report Validation

After the run, check `reports/YYYY-MM-DD_intraday_report.md`:
- Has `# Morning Intraday Stock Scanner Report`
- Has `## Pipeline Summary` table with numeric values (no `?`)
- Has `## Dominant Morning Geopolitical Themes` with headlines
- Has `## Final Selections` with per-ticker metric tables
- Ends with disclaimer

## Scheduler Test

```bash
python -m scanner.scheduler --show
```

Expected: `CRON_TZ=Europe/London`, `0 8 * * 1-5`, references `scanner.main`.

## Error Handling Test

```bash
FINNHUB_API_KEY= python -m scanner.main
```

Expected: `[ERROR] Set FINNHUB_API_KEY in .env file`, exit code 1, no traceback.

## Known Limitations

### Polygon Free Tier — Snapshot Endpoint 403

The `/v2/snapshot/locale/us/markets/stocks/tickers/{TICKER}` endpoint requires a paid plan ($29/mo Starter). On free tier:
- Returns 403 Forbidden
- Pipeline handles gracefully — no crash
- Pre-Market Entry Level = N/A in report
- Pre-Market Volume Ratio = 0.0
- RSI still works (uses `/v2/aggs/ticker/` which IS free)
- Technical scoring uses fallback based on daily bars

This is expected behavior, not a bug. To get full pre-market data, upgrade to Polygon Starter plan.

### Wikipedia Scraping

Wikipedia might block requests without a User-Agent header (returns 403). The code already handles this with a custom User-Agent string. If the scrape fails, it falls back to a local cache file (`scanner/_sp500_cache.csv`).

### Market Hours

The pipeline is designed to run at 08:00 UK time (before US market open). Running outside this window still works but:
- Finnhub company news returns last-24h articles regardless of time
- Polygon daily bars are from prior trading day
- Pre-market data (if snapshot worked) would only be available during pre-market hours (04:00-09:30 ET)

## API Key Verification (Quick Check)

```bash
# Finnhub
curl -s "https://finnhub.io/api/v1/news?category=general&token=$FINNHUB_API_KEY" | python -c "import sys,json; d=json.load(sys.stdin); print(f'{len(d)} headlines')" 

# Polygon
curl -s "https://api.polygon.io/v2/aggs/ticker/AAPL/range/1/day/2026-01-01/2026-01-31?apiKey=$POLYGON_API_KEY" | python -c "import sys,json; d=json.load(sys.stdin); print(f'{d.get(\"resultsCount\", 0)} bars')"
```
