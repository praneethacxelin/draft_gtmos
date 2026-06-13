"""Daily buying-signal scanner.

Runs in the background and, once every 24h per strategy, refreshes buying
signals (SerpAPI) and re-scores leads so the pipeline stays fresh without the
user manually clicking "Run Signals". It records a ``daily_signal_summary`` on
each strategy (new-signal count + biggest rank movers) which powers the
Dashboard "Signal Pulse" card.

Safety:
  - Only scans strategies whose owner has a SerpAPI key configured. With no
    key it does nothing (the dashboard then shows the "add SerpAPI key" hint).
  - Skips a strategy if it was already scanned within the last 24h, so app
    restarts don't burn SerpAPI credits.
  - Every failure is swallowed/logged so the background task never crashes the
    server.
"""
import asyncio
import logging
from datetime import datetime, timedelta

from app.db import SessionLocal, Strategy, Contact, Account
from app.services import settings_service

log = logging.getLogger("gtm.signal_cron")

SCAN_INTERVAL_SECONDS = 24 * 60 * 60
_STARTUP_DELAY_SECONDS = 120
_RESCAN_AFTER = timedelta(hours=24)


def _build_movers(db, strategy_id: str, before: dict[str, float]) -> list[dict]:
    """Compute the contacts whose total_score moved the most since ``before``."""
    rows = (
        db.query(Contact, Account)
        .join(Account, Account.id == Contact.account_id)
        .filter(Contact.strategy_id == strategy_id)
        .all()
    )
    movers = []
    for contact, account in rows:
        prev = before.get(contact.id, 0.0) or 0.0
        curr = contact.total_score or 0.0
        delta = round(curr - prev, 1)
        if abs(delta) < 0.1:
            continue
        movers.append({
            "contact_id": contact.id,
            "contact_name": contact.full_name,
            "title": contact.title,
            "company": account.company_name if account else None,
            "before": round(prev, 1),
            "after": round(curr, 1),
            "delta": delta,
        })
    movers.sort(key=lambda m: m["delta"], reverse=True)
    return movers[:5]


async def scan_strategy(db, strategy: Strategy) -> dict | None:
    """Refresh signals + scores for one strategy and store the summary."""
    # Local import avoids a circular import at module load time.
    from app.agents.s2_signals import run_signals

    before = {
        c.id: (c.total_score or 0.0)
        for c in db.query(Contact).filter(Contact.strategy_id == strategy.id).all()
    }
    result = await run_signals(db, strategy.id)  # also re-runs score_leads

    movers = _build_movers(db, strategy.id, before)
    scanned_at = datetime.utcnow()
    summary = {
        "scanned_at": scanned_at.isoformat(),
        "new_signals": result.get("signals_added", 0) if isinstance(result, dict) else 0,
        "is_demo": result.get("is_demo", False) if isinstance(result, dict) else False,
        "top_movers": movers,
    }
    strategy.daily_signal_summary = summary
    strategy.last_signal_scan = scanned_at
    db.commit()
    return summary


async def _scan_once() -> None:
    db = SessionLocal()
    try:
        strategies = db.query(Strategy).filter(Strategy.status == "ready").all()
        now = datetime.utcnow()
        for strategy in strategies:
            serp_key = settings_service.get_key(db, strategy.user_id, "serpapi")
            if not serp_key:
                continue  # no live signal source for this owner
            last = strategy.last_signal_scan
            if last and (now - last) < _RESCAN_AFTER:
                continue  # already fresh
            try:
                summary = await scan_strategy(db, strategy)
                log.info(
                    "Signal cron scanned '%s': %s new signals",
                    strategy.product_name,
                    summary.get("new_signals") if summary else "?",
                )
            except Exception as exc:
                db.rollback()
                log.warning("Signal cron failed for %s: %s", strategy.id, exc)
    except Exception as exc:
        log.warning("Signal cron pass failed: %s", exc)
    finally:
        db.close()


async def signal_cron_loop() -> None:
    """Background task: scan due strategies roughly once a day."""
    await asyncio.sleep(_STARTUP_DELAY_SECONDS)
    while True:
        try:
            await _scan_once()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.warning("Signal cron loop error: %s", exc)
        await asyncio.sleep(SCAN_INTERVAL_SECONDS)
