"""Standalone weekly broker fee email sender.

Invoked by Windows Task Scheduler every Monday at 09:00 local time.
Runs independently of the FastAPI process — imports `build_and_send_report`
directly and sends via SMTP. Exit code 0 on success, 1 on failure so that
Task Scheduler's "run missed task on wake" logic works correctly.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

if sys.stdout.encoding and "utf" not in sys.stdout.encoding.lower():
    os.environ["PYTHONIOENCODING"] = "utf-8"

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(PROJECT_ROOT / ".env")

log_dir = PROJECT_ROOT / "logs"
log_dir.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(log_dir / "weekly_email.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("send_weekly_email")


def main() -> int:
    try:
        from be_invest.email_sender import build_and_send_report

        logger.info("Starting weekly email send")
        result = build_and_send_report()
        logger.info(
            "Weekly email sent: subject=%s recipients=%d sent_at=%s",
            result["subject"],
            len(result["recipients"]),
            result["sent_at"],
        )
        return 0
    except Exception:
        logger.exception("Weekly email send failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
