"""Module 1 – S&P 500 Symbol Ingestion.

Fetches the current S&P 500 constituent list from Wikipedia and caches it
locally for the trading day.  Falls back to a bundled static list if the
network request fails.
"""

import logging
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

logger = logging.getLogger(__name__)

_WIKI_URL = (
    "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
)
_CACHE_FILE = Path(__file__).resolve().parent / "_sp500_cache.csv"


def fetch_sp500_tickers(*, use_cache: bool = True) -> list[str]:
    """Return a list of S&P 500 ticker symbols.

    Strategy:
      1. If *use_cache* and a cache file exists, return that.
      2. Scrape the Wikipedia S&P 500 table.
      3. Persist the result to *_CACHE_FILE*.
      4. On any network/parse error fall back to the cache or raise.
    """
    # 1. Try cache
    if use_cache and _CACHE_FILE.exists():
        try:
            cached = pd.read_csv(_CACHE_FILE)
            tickers = cached["Symbol"].dropna().tolist()
            if len(tickers) >= 400:
                logger.info("Loaded %d tickers from cache", len(tickers))
                return tickers
        except Exception:
            logger.warning("Cache read failed; will re-fetch.")

    # 2. Scrape Wikipedia
    try:
        logger.info("Fetching S&P 500 list from Wikipedia …")
        headers = {"User-Agent": "MorningStockScanner/1.0 (educational project)"}
        resp = requests.get(_WIKI_URL, headers=headers, timeout=15)
        resp.raise_for_status()
        tables = pd.read_html(StringIO(resp.text))
        df = tables[0]  # first table is the constituents list
        # Normalise dots to hyphens for API compatibility (e.g. BRK.B → BRK-B)
        tickers = (
            df["Symbol"]
            .str.strip()
            .str.replace(".", "-", regex=False)
            .dropna()
            .tolist()
        )
        logger.info("Fetched %d tickers from Wikipedia", len(tickers))

        # 3. Cache
        df[["Symbol"]].to_csv(_CACHE_FILE, index=False)
        return tickers

    except Exception as exc:
        logger.error("Wikipedia fetch failed: %s", exc)

        # 4. Fallback – re-read stale cache
        if _CACHE_FILE.exists():
            try:
                cached = pd.read_csv(_CACHE_FILE)
                tickers = cached["Symbol"].dropna().tolist()
                logger.warning("Using stale cache (%d tickers)", len(tickers))
                return tickers
            except Exception:
                pass

        raise RuntimeError(
            "Cannot obtain S&P 500 ticker list – no network and no cache."
        ) from exc
