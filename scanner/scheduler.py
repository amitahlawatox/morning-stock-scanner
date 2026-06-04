"""Module 8 – Cron Scheduler.

Provides helper utilities to install / display the correct crontab entry
for running the pipeline Monday–Friday at 08:00 Europe/London (handles
GMT ↔ BST automatically via the system timezone).

Usage from CLI:
    python -m scanner.scheduler --install   # add crontab entry
    python -m scanner.scheduler --show      # print the crontab line
"""

import argparse
import logging
import os
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_VENV_PYTHON = _PROJECT_ROOT / "scanner" / ".venv" / "bin" / "python"
_MAIN_SCRIPT = _PROJECT_ROOT / "scanner" / "main.py"

# We use the system timezone approach: set TZ=Europe/London so cron's
# "0 8 * * 1-5" fires at 08:00 local UK time regardless of GMT/BST.
_CRON_LINE = (
    f'CRON_TZ=Europe/London\n'
    f'0 8 * * 1-5 cd {_PROJECT_ROOT} && {_VENV_PYTHON} -m scanner.main '
    f'>> {_PROJECT_ROOT}/scanner.log 2>&1'
)


def get_cron_line() -> str:
    """Return the crontab line to schedule the pipeline."""
    return _CRON_LINE


def install_cron() -> bool:
    """Append the cron entry to the current user's crontab."""
    try:
        # Read existing crontab
        result = subprocess.run(
            ["crontab", "-l"], capture_output=True, text=True
        )
        existing = result.stdout if result.returncode == 0 else ""

        # Check if already installed
        if "scanner.main" in existing:
            logger.info("Cron entry already present – skipping install.")
            return True

        # Append
        new_crontab = existing.rstrip("\n") + "\n\n# Morning Stock Scanner\n" + _CRON_LINE + "\n"
        proc = subprocess.run(
            ["crontab", "-"],
            input=new_crontab,
            capture_output=True,
            text=True,
        )
        if proc.returncode == 0:
            logger.info("Cron entry installed successfully.")
            return True
        else:
            logger.error("crontab install failed: %s", proc.stderr)
            return False

    except Exception as exc:
        logger.error("Failed to install cron: %s", exc)
        return False


def main():
    parser = argparse.ArgumentParser(description="Manage the stock scanner cron schedule")
    parser.add_argument("--install", action="store_true", help="Install the crontab entry")
    parser.add_argument("--show", action="store_true", help="Show the crontab line")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if args.show or not args.install:
        print("=" * 60)
        print("Crontab entry for Morning Stock Scanner:")
        print("=" * 60)
        print()
        print(get_cron_line())
        print()
        print("This runs Mon-Fri at 08:00 Europe/London time (handles GMT/BST).")
        print()

    if args.install:
        success = install_cron()
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
