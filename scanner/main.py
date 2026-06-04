"""Main orchestrator – Morning Stock Scanner Pipeline.

Runs the full pipeline end-to-end:
  1. Ingest S&P 500 symbols
  2. Fetch general news + per-ticker company news
  3. Stage 1: Sentiment filter  (500 → 15)
  4. Stage 2: Geopolitical filter (15 → 10)
  5. Stage 3: Technical filter   (10 → 5)
  6. Stage 4: Stress-test        (5 → 2)
  7. Generate dated Markdown report

Usage:
    python -m scanner.main           # full run
    python -m scanner.main --dry     # symbol ingestion only (quick test)
"""

import argparse
import logging
import sys
import time
from datetime import datetime

import pytz

from .config import FINNHUB_API_KEY, POLYGON_API_KEY
from .data_acquisition import fetch_company_news, fetch_general_news
from .geopolitical import geopolitical_filter
from .notify import send_whatsapp_report
from .regime import regime_filter
from .report import generate_report
from .sentiment import sentiment_filter
from .stress_test import stress_test
from .symbols import fetch_sp500_sectors, fetch_sp500_tickers
from .technicals import technical_filter

logger = logging.getLogger(__name__)


def _setup_logging():
    """Configure root logger for terminal + file output."""
    fmt = "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=fmt,
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )


def _uk_time_str() -> str:
    london = pytz.timezone("Europe/London")
    return datetime.now(london).strftime("%Y-%m-%d %H:%M:%S %Z")


def run_pipeline(*, dry_run: bool = False):
    """Execute the full scanner pipeline."""
    _setup_logging()

    print("=" * 60)
    print("  MORNING STOCK SCANNER PIPELINE")
    print(f"  Started: {_uk_time_str()}")
    print("=" * 60)

    # ── Pre-flight checks ───────────────────────────────────
    if not FINNHUB_API_KEY:
        logger.error("FINNHUB_API_KEY is not set. Aborting.")
        print("\n[ERROR] Set FINNHUB_API_KEY in .env file. See .env.example.")
        sys.exit(1)

    if not POLYGON_API_KEY:
        logger.warning("POLYGON_API_KEY not set – Stage 3 will use fallback scoring.")

    t0 = time.time()

    # ── Step 1: Symbol Ingestion ────────────────────────────
    print("\n[1/8] Fetching S&P 500 tickers …")
    tickers = fetch_sp500_tickers()
    sector_map = fetch_sp500_sectors()
    print(f"       → {len(tickers)} tickers loaded ({len(sector_map)} with sector data)")

    if dry_run:
        print("\n[DRY RUN] Exiting after symbol ingestion.")
        return

    stage_counts = {"universe": len(tickers)}

    # ── Step 2: Data Acquisition ────────────────────────────
    print("\n[2/8] Fetching general market news …")
    general_news = fetch_general_news()
    print(f"       → {len(general_news)} macro headlines")

    print(f"\n[2/8] Scanning company news for {len(tickers)} tickers …")
    print(f"       (estimated time: ~{len(tickers) * 1.1 / 60:.0f} minutes at 1.1s/ticker)")
    company_news = fetch_company_news(tickers)
    tickers_with_news = sum(1 for v in company_news.values() if v)
    print(f"       → {tickers_with_news} tickers had news in last 24h")

    # ── Step 3: Stage 1 – Sentiment Filter ──────────────────
    print("\n[3/8] Stage 1: Sentiment Filter (→ top 15) …")
    stage1 = sentiment_filter(company_news)
    stage_counts["sentiment"] = len(stage1)
    print(f"       → {len(stage1)} tickers passed")
    for s in stage1:
        print(f"         {s['ticker']:6s}  sentiment={s['compound']:.3f}  headlines={s['headline_count']}")

    if not stage1:
        logger.warning("No tickers passed sentiment filter. Generating empty report.")
        report_path = generate_report([], general_news, stage_counts)
        print(f"\n[DONE] Report: {report_path}")
        return

    # ── Step 4: Stage 2 – Geopolitical Filter ───────────────
    print("\n[4/8] Stage 2: Geopolitical Cross-Reference (→ top 10) …")
    stage2 = geopolitical_filter(stage1, company_news, general_news)
    stage_counts["geopolitical"] = len(stage2)
    print(f"       → {len(stage2)} tickers survived")

    if not stage2:
        logger.warning("No tickers survived geopolitical filter.")
        report_path = generate_report([], general_news, stage_counts)
        print(f"\n[DONE] Report: {report_path}")
        return

    # ── Step 4.5: Stage 2.5 – Macro-Regime Sector Alignment ─
    print("\n[5/8] Stage 2.5: Macro-Regime Sector Alignment …")
    stage2_5 = regime_filter(stage2, general_news, sector_map)
    stage_counts["regime"] = len(stage2_5)
    for s in stage2_5:
        theme_str = ", ".join(s.get("regime_themes", [])) or "neutral"
        print(f"         {s['ticker']:6s}  sector={s.get('ticker_sector', '?'):25s}  regime={theme_str:15s}  boost={s.get('regime_score', 0):+.0f}")
    print(f"       → {len(stage2_5)} tickers re-ranked by regime alignment")

    # ── Step 6: Stage 3 – Technical Filter ──────────────────
    print(f"\n[6/8] Stage 3: Pre-Market Technical Filter (→ top 5) …")
    print(f"       (estimated time: ~{len(stage2_5) * 12 / 60:.0f} minutes at 12s/ticker)")
    stage3 = technical_filter(stage2_5)
    stage_counts["technical"] = len(stage3)
    print(f"       → {len(stage3)} tickers shortlisted")

    if not stage3:
        logger.warning("No tickers survived technical filter.")
        report_path = generate_report([], general_news, stage_counts)
        print(f"\n[DONE] Report: {report_path}")
        return

    # ── Step 7: Stage 4 – Stress-Test ───────────────────────
    print("\n[7/8] Stage 4: Devil's Advocate Stress-Test (→ top 2) …")
    stage4 = stress_test(stage3)
    stage_counts["stress"] = len(stage4)
    print(f"       → {len(stage4)} tickers survived")

    # ── Step 8: Report Generation ───────────────────────────
    print("\n[8/8] Generating Markdown report …")
    report_path = generate_report(stage4, general_news, stage_counts)
    print(f"       → Report saved: {report_path}")

    # ── WhatsApp Notification ─────────────────────────────────
    from pathlib import Path
    report_content = Path(report_path).read_text(encoding="utf-8")
    print("\n[NOTIFY] Sending report via WhatsApp …")
    if send_whatsapp_report(report_content):
        print("       → WhatsApp message sent successfully")
    else:
        print("       → WhatsApp notification skipped (check config/logs)")

    elapsed = time.time() - t0
    print("\n" + "=" * 60)
    print(f"  PIPELINE COMPLETE")
    print(f"  Finished: {_uk_time_str()}")
    print(f"  Elapsed:  {elapsed / 60:.1f} minutes")
    print(f"  Final picks: {[c['ticker'] for c in stage4]}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Morning Stock Scanner Pipeline")
    parser.add_argument(
        "--dry", action="store_true",
        help="Dry run: only fetch tickers, skip API-heavy stages",
    )
    args = parser.parse_args()
    run_pipeline(dry_run=args.dry)


if __name__ == "__main__":
    main()
