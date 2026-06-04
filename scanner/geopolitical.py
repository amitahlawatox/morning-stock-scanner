"""Stage 2 – Geopolitical Macro Cross-Reference (15 → 10).

Builds a defensive keyword filtering matrix and scans company news +
global macro headlines for geopolitical risk exposure.  Eliminates the 5
most-exposed tickers.
"""

import logging
import re

from .config import GEO_RISK_KEYWORDS, GEO_SURVIVORS

logger = logging.getLogger(__name__)

_PATTERNS = [
    re.compile(rf"\b{re.escape(kw)}\b", re.IGNORECASE)
    for kw in GEO_RISK_KEYWORDS
]


def _count_risk_hits(texts: list[str]) -> int:
    """Count how many risk-keyword matches appear across *texts*."""
    total = 0
    for text in texts:
        for pat in _PATTERNS:
            total += len(pat.findall(text))
    return total


def geopolitical_filter(
    candidates: list[dict],
    company_news: dict[str, list[dict]],
    general_news: list[dict],
    survivors: int = GEO_SURVIVORS,
) -> list[dict]:
    """Cross-reference candidates against geo-risk keywords.

    Returns the *survivors* tickers with the LOWEST risk exposure.
    """
    macro_texts = [
        (a.get("headline", "") or "") + " " + (a.get("summary", "") or "")
        for a in general_news
    ]
    macro_hits = _count_risk_hits(macro_texts)
    logger.info(
        "Global macro risk hits: %d across %d headlines",
        macro_hits, len(macro_texts),
    )

    scored: list[dict] = []

    for cand in candidates:
        ticker = cand["ticker"]
        articles = company_news.get(ticker, [])
        ticker_texts = [
            (a.get("headline", "") or "") + " " + (a.get("summary", "") or "")
            for a in articles
        ]
        risk_hits = _count_risk_hits(ticker_texts)
        scored.append({**cand, "geo_risk_hits": risk_hits})

    # Sort by risk ascending (least risky first) → keep top *survivors*
    scored.sort(key=lambda x: x["geo_risk_hits"])
    kept = scored[:survivors]

    eliminated = scored[survivors:]
    logger.info(
        "Geo filter: keeping %d, eliminating %d",
        len(kept), len(eliminated),
    )
    for item in eliminated:
        logger.debug(
            "  ELIMINATED %s  risk_hits=%d",
            item["ticker"], item["geo_risk_hits"],
        )

    return kept
