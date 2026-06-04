"""Module 2 – Local Data Acquisition & Macro Tracking.

- Fetches top global/macro headlines from Finnhub general news.
- Loops through all S&P 500 tickers and pulls last-24-hour company news.
- Enforces strict 1.1-second sleep between each ticker request.
"""

import logging
import time
from datetime import datetime, timedelta

import pytz
import requests

from .config import FINNHUB_API_KEY, FINNHUB_DELAY

logger = logging.getLogger(__name__)

_FINNHUB_BASE = "https://finnhub.io/api/v1"


def _finnhub_get(endpoint: str, params: dict | None = None) -> dict | list:
    """Make an authenticated GET to Finnhub and return JSON."""
    params = params or {}
    params["token"] = FINNHUB_API_KEY
    url = f"{_FINNHUB_BASE}/{endpoint}"
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def fetch_general_news(category: str = "general") -> list[dict]:
    """Fetch top macro/geopolitical morning headlines from Finnhub."""
    try:
        news = _finnhub_get("news", {"category": category})
        logger.info("Fetched %d general news items", len(news))
        return news
    except Exception as exc:
        logger.error("General news fetch failed: %s", exc)
        return []


def fetch_company_news(
    tickers: list[str],
) -> dict[str, list[dict]]:
    """Query Finnhub /company-news for each ticker (last 24 h).

    Returns {ticker: [article_dict, …]}.
    Sleeps *FINNHUB_DELAY* seconds between requests.
    """
    london = pytz.timezone("Europe/London")
    now_uk = datetime.now(london)
    date_to = now_uk.strftime("%Y-%m-%d")
    date_from = (now_uk - timedelta(days=1)).strftime("%Y-%m-%d")

    results: dict[str, list[dict]] = {}
    total = len(tickers)

    for idx, ticker in enumerate(tickers, 1):
        try:
            articles = _finnhub_get(
                "company-news",
                {"symbol": ticker, "from": date_from, "to": date_to},
            )
            results[ticker] = articles if isinstance(articles, list) else []
            if idx % 50 == 0 or idx == total:
                logger.info(
                    "[news] %d / %d tickers scanned (%s)",
                    idx, total, ticker,
                )
        except Exception as exc:
            logger.warning("Company news failed for %s: %s", ticker, exc)
            results[ticker] = []

        # Rate-limit guard
        time.sleep(FINNHUB_DELAY)

    return results
