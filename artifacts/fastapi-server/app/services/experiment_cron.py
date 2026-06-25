"""Live-experiment evaluation loop.

Every ``EXP_EVAL_INTERVAL_SEC`` the loop closes out any live experiment whose
window has elapsed: it scores each variant by positive-intent reply rate (a
reply that books a call / meeting) and crowns the live winner. This is what
makes an "experiment" a real one-window learning loop rather than a one-shot
lead pull.
"""
from __future__ import annotations

import asyncio
import logging

from app.db import SessionLocal
from app.agents.live_experiment import evaluate_due_batches

log = logging.getLogger("gtm.experiment_cron")

# Check hourly; windows are month-long so this cadence is plenty.
EXP_EVAL_INTERVAL_SEC = 60 * 60
STARTUP_DELAY_SEC = 90


async def experiment_eval_loop() -> None:
    """Background task: evaluate experiment windows that have closed."""
    await asyncio.sleep(STARTUP_DELAY_SEC)
    while True:
        try:
            db = SessionLocal()
            try:
                n = await asyncio.to_thread(evaluate_due_batches, db)
                if n:
                    log.info("evaluated %d live experiment window(s)", n)
            finally:
                db.close()
        except Exception as exc:  # pragma: no cover
            log.exception("experiment eval loop crashed: %s", exc)
        await asyncio.sleep(EXP_EVAL_INTERVAL_SEC)
