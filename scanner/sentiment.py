"""Stage 1 – Local Sentiment Filter (500 → 15).

Uses VADER to score every headline collected per ticker.
Filters out tickers with zero news and ranks by compound positive
sentiment, keeping the top N.
"""

import logging

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from .config import SENTIMENT_TOP_N

logger = logging.getLogger(__name__)

_vader = SentimentIntensityAnalyzer()


def _score_headlines(articles: list[dict]) -> dict:
    """Return aggregate sentiment metrics for a list of articles."""
    if not articles:
        return {
            "compound": 0.0,
            "headline_count": 0,
            "best_headline": "",
            "best_score": 0.0,
        }

    compounds: list[float] = []
    best_score = -999.0
    best_headline = ""

    for art in articles:
        headline = art.get("headline", "") or ""
        if not headline:
            continue
        scores = _vader.polarity_scores(headline)
        compounds.append(scores["compound"])
        if scores["compound"] > best_score:
            best_score = scores["compound"]
            best_headline = headline

    if not compounds:
        return {
            "compound": 0.0,
            "headline_count": 0,
            "best_headline": "",
            "best_score": 0.0,
        }

    avg = sum(compounds) / len(compounds)
    return {
        "compound": avg,
        "headline_count": len(compounds),
        "best_headline": best_headline,
        "best_score": best_score,
    }


def sentiment_filter(
    company_news: dict[str, list[dict]],
    top_n: int = SENTIMENT_TOP_N,
) -> list[dict]:
    """Score all tickers and return the top *top_n* by compound sentiment.

    Returns a list of dicts:
        [{ticker, compound, headline_count, best_headline, best_score}, …]
    """
    scored: list[dict] = []

    for ticker, articles in company_news.items():
        metrics = _score_headlines(articles)
        if metrics["headline_count"] == 0:
            continue  # skip tickers with zero active news
        scored.append({"ticker": ticker, **metrics})

    # Rank by compound positive sentiment (descending)
    scored.sort(key=lambda x: x["compound"], reverse=True)
    top = scored[:top_n]

    logger.info(
        "Sentiment filter: %d tickers had news → top %d selected",
        len(scored),
        len(top),
    )
    for item in top:
        logger.debug(
            "  %s  compound=%.3f  headlines=%d",
            item["ticker"],
            item["compound"],
            item["headline_count"],
        )

    return top
