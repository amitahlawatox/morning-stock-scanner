"""Stage 2.5 – Macro-Regime Sector Alignment Filter.

Identifies the dominant macro theme from today's headlines and re-ranks
pipeline candidates to favor tickers whose GICS sector aligns with the
prevailing regime.  Off-theme tickers are penalized; on-theme tickers
are boosted.

This bridges the gap between pure sentiment scoring and sector-aware
thematic trading — ensuring the final picks match the day's narrative.
"""

import logging
import re

logger = logging.getLogger(__name__)

# ── Theme keyword clusters mapped to GICS sectors ──────────────────
# Each theme has keywords and the GICS sectors/sub-industries it maps to.
REGIME_THEMES: dict[str, dict] = {
    "Energy": {
        "keywords": [
            "oil", "crude", "opec", "natural gas", "petroleum",
            "pipeline", "drilling", "refinery", "shale", "lng",
            "brent", "wti", "gasoline", "fuel", "energy crisis",
        ],
        "sectors": ["Energy"],
        "sub_industries": [],
    },
    "Defence": {
        "keywords": [
            "military", "missile", "weapons", "defence", "defense",
            "nato", "war", "invasion", "airspace", "navy", "army",
            "troops", "strike", "ceasefire", "attack", "conflict",
            "bomb", "fighter jet", "drone strike", "artillery",
        ],
        "sectors": [],  # Defence is under Industrials, use sub_industry
        "sub_industries": ["Aerospace & Defense"],
    },
    "Technology": {
        "keywords": [
            "artificial intelligence", "ai", "semiconductor", "chip",
            "cloud computing", "software", "data center", "quantum",
            "cybersecurity", "tech earnings", "nvidia", "openai",
        ],
        "sectors": ["Information Technology"],
        "sub_industries": [],
    },
    "Healthcare": {
        "keywords": [
            "fda", "drug approval", "pharma", "clinical trial",
            "biotech", "vaccine", "treatment", "healthcare",
            "medical device", "hospital",
        ],
        "sectors": ["Health Care"],
        "sub_industries": [],
    },
    "Financials": {
        "keywords": [
            "interest rate", "fed rate", "federal reserve", "yield",
            "banking crisis", "credit", "mortgage", "treasury",
            "bonds", "rate cut", "rate hike", "monetary policy",
        ],
        "sectors": ["Financials"],
        "sub_industries": [],
    },
    "Commodities": {
        "keywords": [
            "mining", "steel", "copper", "lithium", "gold price",
            "silver", "rare earth", "commodity", "iron ore",
            "aluminum", "nickel",
        ],
        "sectors": ["Materials"],
        "sub_industries": [],
    },
}

# Pre-compile patterns for each theme
_THEME_PATTERNS: dict[str, list[re.Pattern]] = {}
for _theme, _cfg in REGIME_THEMES.items():
    _THEME_PATTERNS[_theme] = [
        re.compile(rf"\b{re.escape(kw)}\b", re.IGNORECASE)
        for kw in _cfg["keywords"]
    ]


def identify_dominant_themes(
    general_news: list[dict],
    top_n: int = 2,
) -> list[tuple[str, int]]:
    """Score macro headlines against theme keyword clusters.

    Returns top *top_n* themes as [(theme_name, hit_count), ...] sorted
    by hit count descending.
    """
    texts = [
        (a.get("headline", "") or "") + " " + (a.get("summary", "") or "")
        for a in general_news
    ]
    combined = " ".join(texts)

    theme_scores: dict[str, int] = {}
    for theme, patterns in _THEME_PATTERNS.items():
        hits = sum(len(p.findall(combined)) for p in patterns)
        theme_scores[theme] = hits

    ranked = sorted(theme_scores.items(), key=lambda x: x[1], reverse=True)
    dominant = [(t, s) for t, s in ranked[:top_n] if s > 0]

    logger.info(
        "Regime detection — all themes: %s",
        ", ".join(f"{t}={s}" for t, s in ranked),
    )
    logger.info(
        "Dominant themes: %s",
        ", ".join(f"{t} ({s} hits)" for t, s in dominant) or "NONE",
    )

    return dominant


def _ticker_matches_theme(
    ticker: str,
    theme_name: str,
    sector_map: dict[str, dict],
) -> bool:
    """Check if a ticker's sector/sub-industry aligns with a theme."""
    info = sector_map.get(ticker, {})
    if not info:
        return False

    theme_cfg = REGIME_THEMES[theme_name]
    ticker_sector = info.get("sector", "")
    ticker_sub = info.get("sub_industry", "")

    # Check sector match
    if ticker_sector in theme_cfg["sectors"]:
        return True

    # Check sub-industry match (for Defence under Industrials, etc.)
    for sub in theme_cfg["sub_industries"]:
        if sub.lower() in ticker_sub.lower():
            return True

    return False


def regime_filter(
    candidates: list[dict],
    general_news: list[dict],
    sector_map: dict[str, dict],
    regime_boost: float = 30.0,
    off_theme_penalty: float = 15.0,
) -> list[dict]:
    """Re-rank candidates by macro-regime sector alignment.

    - Tickers in the dominant theme's sector(s) get a score boost.
    - Tickers in off-theme defensive sectors get a penalty.
    - Neutral tickers pass through with base score.

    Returns all candidates re-sorted by adjusted score (highest first),
    preserving the same count (no elimination here — just re-ordering
    so Stage 3 processes regime-aligned tickers first).
    """
    if not sector_map:
        logger.warning("No sector data — skipping regime filter")
        return candidates

    dominant_themes = identify_dominant_themes(general_news)

    if not dominant_themes:
        logger.info("No dominant theme detected — passing candidates through unchanged")
        return candidates

    # Defensive sectors that underperform in inflationary/risk-on regimes
    DEFENSIVE_SECTORS = {"Consumer Staples", "Utilities", "Real Estate"}

    scored = []
    for cand in candidates:
        ticker = cand["ticker"]
        regime_score = 0.0
        matched_themes = []

        for theme_name, _hits in dominant_themes:
            if _ticker_matches_theme(ticker, theme_name, sector_map):
                regime_score += regime_boost
                matched_themes.append(theme_name)

        # Penalize defensive sectors when dominant theme is risk-on
        info = sector_map.get(ticker, {})
        ticker_sector = info.get("sector", "")
        if ticker_sector in DEFENSIVE_SECTORS and not matched_themes:
            regime_score -= off_theme_penalty

        scored.append({
            **cand,
            "regime_score": regime_score,
            "regime_themes": matched_themes,
            "ticker_sector": ticker_sector,
        })

        if matched_themes:
            logger.info(
                "  REGIME BOOST  %s  sector=%s  themes=%s  +%.0f",
                ticker, ticker_sector, matched_themes, regime_score,
            )
        elif regime_score < 0:
            logger.info(
                "  REGIME PENALTY  %s  sector=%s (defensive, off-theme)  %.0f",
                ticker, ticker_sector, regime_score,
            )

    # Sort by regime_score descending, then by original sentiment as tiebreak
    scored.sort(
        key=lambda x: (x["regime_score"], x.get("compound", 0)),
        reverse=True,
    )

    return scored
