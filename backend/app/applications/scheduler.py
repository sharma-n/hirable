from __future__ import annotations

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler

from app.applications.automation import apply_automation
from app.db.engine import SessionLocal

logger = logging.getLogger("app.applications.scheduler")


def run_automation_once() -> None:
    """Runs apply_automation against a fresh session. Used both for the daily
    scheduled job and the one-off startup pass — the scheduler job's DB
    session must be self-managed since it runs outside the request cycle
    (get_db's FastAPI dependency-injection lifecycle isn't available here)."""
    db = SessionLocal()
    try:
        apply_automation(db, datetime.now(timezone.utc))
    except Exception:
        logger.exception("applications automation run failed")
    finally:
        db.close()


def build_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler()
    scheduler.add_job(run_automation_once, "interval", days=1, id="applications_automation")
    return scheduler
