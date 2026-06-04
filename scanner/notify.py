"""WhatsApp notification via Twilio.

Sends the daily report summary to the configured WhatsApp number
after the pipeline completes.
"""

import logging

from twilio.rest import Client

from .config import (
    TWILIO_ACCOUNT_SID,
    TWILIO_AUTH_TOKEN,
    TWILIO_WHATSAPP_FROM,
    WHATSAPP_TO,
)

logger = logging.getLogger(__name__)

# Twilio WhatsApp sandbox sender (default) or your approved number
_DEFAULT_FROM = "whatsapp:+14155238886"


def send_whatsapp_report(report_text: str) -> bool:
    """Send the report summary via WhatsApp.

    Args:
        report_text: The Markdown report content (will be truncated for
                     WhatsApp's 1600-char message limit).

    Returns:
        True if message sent successfully, False otherwise.
    """
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
        logger.warning("Twilio credentials not set — skipping WhatsApp notification")
        return False

    if not WHATSAPP_TO:
        logger.warning("WHATSAPP_TO not set — skipping notification")
        return False

    from_number = TWILIO_WHATSAPP_FROM or _DEFAULT_FROM
    to_number = f"whatsapp:{WHATSAPP_TO}" if not WHATSAPP_TO.startswith("whatsapp:") else WHATSAPP_TO

    # Build a concise message for WhatsApp (1600 char limit)
    summary = _build_whatsapp_summary(report_text)

    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        message = client.messages.create(
            from_=from_number,
            to=to_number,
            body=summary,
        )
        logger.info("WhatsApp message sent: SID=%s", message.sid)
        return True

    except Exception as exc:
        logger.error("WhatsApp send failed: %s", exc)
        return False


def _build_whatsapp_summary(report_text: str) -> str:
    """Extract key info from Markdown report into a WhatsApp-friendly message."""
    lines = report_text.split("\n")

    # Extract date
    date_line = ""
    for line in lines:
        if line.startswith("## 20"):
            date_line = line.replace("## ", "").strip()
            break

    # Extract final picks section
    picks_section = []
    in_picks = False
    for line in lines:
        if "Final Selections" in line:
            in_picks = True
            picks_section.append(line.replace("## ", "").replace("#", "").strip())
            continue
        if in_picks:
            if line.startswith("---"):
                break
            if line.startswith("### "):
                picks_section.append(f"\n*{line.replace('### ', '')}*")
            elif "Positive Sentiment Score" in line:
                val = line.split("|")[-2].strip() if "|" in line else ""
                picks_section.append(f"  Sentiment: {val}")
            elif "Primary Positive Headline" in line:
                val = line.split("|")[-2].strip() if "|" in line else ""
                picks_section.append(f"  Headline: {val[:100]}")
            elif "RSI (14)" in line:
                val = line.split("|")[-2].strip() if "|" in line else ""
                picks_section.append(f"  RSI: {val}")
            elif "Sector |" in line and "GICS" not in line:
                val = line.split("|")[-2].strip() if "|" in line else ""
                picks_section.append(f"  Sector: {val}")
            elif "Regime Alignment" in line:
                val = line.split("|")[-2].strip() if "|" in line else ""
                picks_section.append(f"  Regime: {val}")

    # Extract dominant themes (first 3)
    themes = []
    in_themes = False
    for line in lines:
        if "Geopolitical Themes" in line:
            in_themes = True
            continue
        if in_themes:
            if line.startswith("---"):
                break
            if line.startswith("- "):
                themes.append(line[2:].strip()[:80])
                if len(themes) >= 3:
                    break

    # Compose message
    msg_parts = [
        f"📊 *Morning Stock Scanner Report*",
        f"📅 {date_line}",
        "",
    ]

    if themes:
        msg_parts.append("🌍 *Top Macro Themes:*")
        for t in themes:
            msg_parts.append(f"  • {t}")
        msg_parts.append("")

    if picks_section:
        msg_parts.append("🎯 " + picks_section[0])
        for p in picks_section[1:]:
            msg_parts.append(p)
    else:
        msg_parts.append("_No tickers survived the pipeline today._")

    msg_parts.extend([
        "",
        "⚠️ _Not financial advice. Do your own due diligence._",
    ])

    summary = "\n".join(msg_parts)

    # Truncate if needed (WhatsApp limit ~1600 chars)
    if len(summary) > 1550:
        summary = summary[:1547] + "..."

    return summary
