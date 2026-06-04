"""Stage 3 – Pre-Market Technical Filtration (10 → 5).

Queries Polygon.io for pre-market / previous-day data for each candidate
ticker, computes RSI and volume metrics via pandas-ta, and shortlists the
top N with the healthiest technicals.
"""

import logging
import time
from datetime import datetime, timedelta

import pandas as pd
import pandas_ta as ta
import pytz
import requests

from .config import (
    POLYGON_API_KEY,
    POLYGON_DELAY,
    RSI_HIGH,
    RSI_LOW,
    TECHNICAL_TOP_N,
)

logger = logging.getLogger(__name__)

_POLYGON_BASE = "https://api.polygon.io"


def _polygon_get(path: str, params: dict | None = None) -> dict:
    """Authenticated GET to Polygon.io."""
    params = params or {}
    params["apiKey"] = POLYGON_API_KEY
    url = f"{_POLYGON_BASE}{path}"
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def _fetch_daily_bars(ticker: str, days: int = 30) -> pd.DataFrame:
    """Fetch recent daily OHLCV bars for *ticker* from Polygon."""
    london = pytz.timezone("Europe/London")
    end = datetime.now(london)
    start = end - timedelta(days=days)
    path = f"/v2/aggs/ticker/{ticker}/range/1/day/{start.strftime('%Y-%m-%d')}/{end.strftime('%Y-%m-%d')}"
    data = _polygon_get(path, {"adjusted": "true", "sort": "asc", "limit": 120})
    results = data.get("results", [])
    if not results:
        return pd.DataFrame()

    df = pd.DataFrame(results)
    df = df.rename(columns={
        "o": "open", "h": "high", "l": "low", "c": "close", "v": "volume",
    })
    return df


def _fetch_premarket_snapshot(ticker: str) -> dict | None:
    """Fetch real-time pre-market snapshot for *ticker*."""
    try:
        data = _polygon_get(f"/v2/snapshot/locale/us/markets/stocks/tickers/{ticker}")
        return data.get("ticker", {})
    except Exception as exc:
        logger.warning("Snapshot fetch failed for %s: %s", ticker, exc)
        return None


def _compute_technicals(df: pd.DataFrame) -> dict:
    """Compute RSI, average volume, and price velocity from daily bars."""
    if df.empty or len(df) < 14:
        return {"rsi": None, "avg_volume": 0, "price_velocity": 0.0}

    rsi_series = ta.rsi(df["close"], length=14)
    rsi_val = rsi_series.iloc[-1] if rsi_series is not None and not rsi_series.empty else None

    avg_volume = df["volume"].mean()

    # Price velocity: % change over last 5 bars
    if len(df) >= 5:
        velocity = (df["close"].iloc[-1] - df["close"].iloc[-5]) / df["close"].iloc[-5] * 100
    else:
        velocity = 0.0

    return {
        "rsi": rsi_val,
        "avg_volume": avg_volume,
        "price_velocity": velocity,
    }


def technical_filter(
    candidates: list[dict],
    top_n: int = TECHNICAL_TOP_N,
) -> list[dict]:
    """Screen candidates on pre-market technicals; return top *top_n*.

    Criteria:
    - RSI between RSI_LOW and RSI_HIGH (momentum without overbought)
    - Strong pre-market volume relative to average daily volume
    - Clear upward price velocity
    """
    if not POLYGON_API_KEY:
        logger.error("POLYGON_API_KEY not set – skipping technical filter")
        return candidates[:top_n]

    scored: list[dict] = []
    total = len(candidates)

    for idx, cand in enumerate(candidates, 1):
        ticker = cand["ticker"]
        logger.info("[technicals] %d / %d  processing %s", idx, total, ticker)

        try:
            # Fetch daily bars for RSI / velocity
            df = _fetch_daily_bars(ticker)
            techs = _compute_technicals(df)

            # Fetch pre-market snapshot
            snapshot = _fetch_premarket_snapshot(ticker)
            premarket_price = None
            premarket_volume = 0
            if snapshot:
                pm = snapshot.get("todaysChange", 0)
                premarket_price = snapshot.get("lastTrade", {}).get("p") or snapshot.get("day", {}).get("c")
                premarket_volume = snapshot.get("day", {}).get("v", 0) or 0
                # Use min data if available
                if snapshot.get("min"):
                    premarket_price = snapshot["min"].get("c") or premarket_price
                    premarket_volume = snapshot["min"].get("av", 0) or premarket_volume

            # Volume ratio: pre-market vs average daily
            volume_ratio = (
                premarket_volume / techs["avg_volume"]
                if techs["avg_volume"] > 0
                else 0
            )

            rsi = techs["rsi"]
            velocity = techs["price_velocity"]

            # Score: higher is better
            # Bonus for RSI in sweet spot, positive velocity, strong volume
            tech_score = 0.0
            rsi_ok = False
            if rsi is not None and RSI_LOW <= rsi <= RSI_HIGH:
                rsi_ok = True
                tech_score += 30  # RSI in healthy range
            if velocity > 0:
                tech_score += min(velocity * 5, 30)  # cap at 30
            tech_score += min(volume_ratio * 10, 40)  # cap at 40

            scored.append({
                **cand,
                "rsi": round(rsi, 2) if rsi is not None else None,
                "rsi_ok": rsi_ok,
                "price_velocity": round(velocity, 3),
                "premarket_price": premarket_price,
                "premarket_volume": premarket_volume,
                "volume_ratio": round(volume_ratio, 3),
                "tech_score": round(tech_score, 2),
            })

        except Exception as exc:
            logger.error("Technical analysis failed for %s: %s", ticker, exc)
            scored.append({**cand, "tech_score": 0, "rsi": None, "rsi_ok": False,
                           "price_velocity": 0, "premarket_price": None,
                           "premarket_volume": 0, "volume_ratio": 0})

        # Rate-limit guard (12-second sleep for Polygon free tier)
        if idx < total:
            time.sleep(POLYGON_DELAY)

    # Rank by tech_score descending
    scored.sort(key=lambda x: x["tech_score"], reverse=True)
    top = scored[:top_n]

    logger.info("Technical filter: top %d selected from %d", len(top), len(scored))
    for item in top:
        logger.debug(
            "  %s  score=%.1f  RSI=%s  vel=%.2f%%  vol_ratio=%.2f",
            item["ticker"], item["tech_score"],
            item.get("rsi", "N/A"), item.get("price_velocity", 0),
            item.get("volume_ratio", 0),
        )

    return top
