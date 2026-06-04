"""Central configuration for the stock scanner pipeline."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

# ── API Keys ────────────────────────────────────────────────
FINNHUB_API_KEY: str = os.getenv("FINNHUB_API_KEY", "")
POLYGON_API_KEY: str = os.getenv("POLYGON_API_KEY", "")

# ── Twilio / WhatsApp ────────────────────────────────────────
TWILIO_ACCOUNT_SID: str = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_WHATSAPP_FROM: str = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
WHATSAPP_TO: str = os.getenv("WHATSAPP_TO", "")

# ── Rate-limit delays (seconds) ─────────────────────────────
FINNHUB_DELAY: float = 1.1   # ~54 calls/min → safely under 60/min
POLYGON_DELAY: float = 12.0  # 5 calls/min on free tier

# ── Pipeline filter thresholds ──────────────────────────────
SENTIMENT_TOP_N: int = 15        # Stage 1 output count
GEO_SURVIVORS: int = 10          # Stage 2 output count
TECHNICAL_TOP_N: int = 5         # Stage 3 output count
STRESS_SURVIVORS: int = 2        # Stage 4 output count

RSI_LOW: float = 45.0
RSI_HIGH: float = 68.0

RESISTANCE_PROXIMITY_PCT: float = 0.5   # % distance to resistance
VOLUME_DRY_UP_THRESHOLD: float = 0.7    # ratio: recent vs earlier volume

# ── Geopolitical risk keywords ──────────────────────────────
GEO_RISK_KEYWORDS: list[str] = [
    "tariffs",
    "oil",
    "crude",
    "regulatory halt",
    "supply chain bottleneck",
    "escalation",
]

# ── Report output directory ─────────────────────────────────
REPORTS_DIR: Path = _PROJECT_ROOT / "reports"
REPORTS_DIR.mkdir(exist_ok=True)
