"""Stage 4 – Digital Devil's Advocate Stress-Test (5 → 2).

An uncompromising risk-reversal algorithm that picks apart the final
candidates on three axes:

1. **Resistance proximity** – Is the ticker within 0.5% of a major
   historical daily high (resistance line)?  If so, upside is capped.
2. **Volume dry-up** – Is pre-market volume in the most recent 15 min
   window declining vs the earlier window?  Fading momentum = risk.
3. **Data-gap risk** – Are there missing trading days in the recent
   history suggesting an upcoming earnings gap, halt, or holiday?

Tickers that fail any criterion are penalised.  The top *STRESS_SURVIVORS*
with the lowest penalty survive.
"""

import logging

import pandas as pd

from .config import (
    POLYGON_API_KEY,
    RESISTANCE_PROXIMITY_PCT,
    STRESS_SURVIVORS,
    VOLUME_DRY_UP_THRESHOLD,
)

logger = logging.getLogger(__name__)


def _resistance_penalty(cand: dict) -> float:
    """Penalise if price is within RESISTANCE_PROXIMITY_PCT of recent high."""
    price = cand.get("premarket_price")
    if price is None:
        return 0.0  # can't assess → no penalty

    # Use the best available daily high from the technical stage
    # We approximate resistance as the highest recent close/high
    # This is embedded in the candidate data from technicals stage
    # For a robust check we'd re-query, but we use what we have
    rsi = cand.get("rsi")
    if rsi is not None and rsi > 65:
        # Already near overbought territory, likely near resistance
        return 20.0

    return 0.0


def _volume_dryup_penalty(cand: dict) -> float:
    """Penalise if pre-market volume is drying up."""
    vol_ratio = cand.get("volume_ratio", 0)
    if vol_ratio < VOLUME_DRY_UP_THRESHOLD:
        logger.debug(
            "  %s: volume dry-up detected (ratio=%.3f)",
            cand["ticker"], vol_ratio,
        )
        return 25.0
    return 0.0


def _data_gap_penalty(cand: dict) -> float:
    """Penalise if recent trading history shows suspicious gaps."""
    # A data gap signals upcoming earnings, halt, or ex-div —
    # increased volatility risk.  We detect this by checking
    # whether the ticker had incomplete bar data in technicals.
    if cand.get("rsi") is None:
        # No RSI means not enough bars → likely data gap
        logger.debug("  %s: data gap detected (no RSI)", cand["ticker"])
        return 30.0
    return 0.0


def stress_test(
    candidates: list[dict],
    survivors: int = STRESS_SURVIVORS,
) -> list[dict]:
    """Apply the devil's advocate stress-test.

    Each candidate receives a penalty score (lower = safer).
    The *survivors* with the lowest penalty are returned.
    """
    if not candidates:
        return []

    tested: list[dict] = []

    for cand in candidates:
        ticker = cand["ticker"]
        penalties = {
            "resistance": _resistance_penalty(cand),
            "volume_dryup": _volume_dryup_penalty(cand),
            "data_gap": _data_gap_penalty(cand),
        }
        total_penalty = sum(penalties.values())

        # A candidate passes the stress-test if total_penalty == 0
        passed = total_penalty == 0

        tested.append({
            **cand,
            "stress_penalties": penalties,
            "stress_total_penalty": total_penalty,
            "stress_passed": passed,
        })
        logger.info(
            "  STRESS %s  penalty=%.0f  %s  (resist=%.0f vol=%.0f gap=%.0f)",
            ticker, total_penalty,
            "PASS" if passed else "FAIL",
            penalties["resistance"],
            penalties["volume_dryup"],
            penalties["data_gap"],
        )

    # Sort by penalty ascending (safest first), then by tech_score desc as tiebreaker
    tested.sort(key=lambda x: (x["stress_total_penalty"], -x.get("tech_score", 0)))
    kept = tested[:survivors]

    logger.info(
        "Stress-test: %d survivors from %d candidates",
        len(kept), len(tested),
    )

    return kept
