"""Ingestion run auditing.

Every backfill/sync wraps its work in ``ingestion_run(...)`` which writes a row
to ``ingestion_runs`` (start, finish, duration, rows written, error count,
final status) so failures on either the PandaScore or vlr.gg path are visible
after the fact. Unmatched-row details for reconciliation are appended to the
run ``message``.
"""
from __future__ import annotations

import logging
import time
import traceback
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterator

from ..db.base import session_scope
from ..db.models import IngestionRun

logger = logging.getLogger("ingest")


@dataclass
class RunStats:
    rows_written: int = 0
    errors: int = 0
    notes: list[str] = field(default_factory=list)

    def add_rows(self, n: int = 1) -> None:
        self.rows_written += n

    def add_error(self, msg: str) -> None:
        self.errors += 1
        self.notes.append(msg)
        logger.warning("ingest error: %s", msg)

    def note(self, msg: str) -> None:
        self.notes.append(msg)
        logger.info(msg)


@contextmanager
def ingestion_run(source: str, job: str) -> Iterator[RunStats]:
    """Context manager that records an ingestion run to the DB."""
    stats = RunStats()
    started = time.monotonic()
    started_at = datetime.now(timezone.utc)

    # Persist a "running" row up front so an in-flight/crashed run is visible.
    with session_scope() as s:
        run = IngestionRun(
            source=source, job=job, started_at=started_at, status="running"
        )
        s.add(run)
        s.flush()
        run_id = run.id

    logger.info("ingestion run %s started (source=%s job=%s)", run_id, source, job)
    final_status = "success"
    error_message: str | None = None
    try:
        yield stats
    except Exception:  # noqa: BLE001 - we re-raise after recording
        final_status = "failed"
        error_message = traceback.format_exc()
        stats.errors += 1
        raise
    finally:
        if final_status != "failed" and stats.errors:
            final_status = "partial"
        message = error_message or ("\n".join(stats.notes) if stats.notes else None)
        # Postgres text columns can't hold unbounded messages comfortably.
        if message and len(message) > 8000:
            message = message[:8000] + "\n...[truncated]"
        duration = round(time.monotonic() - started, 3)
        with session_scope() as s:
            run = s.get(IngestionRun, run_id)
            if run is not None:
                run.finished_at = datetime.now(timezone.utc)
                run.duration_seconds = duration
                run.rows_written = stats.rows_written
                run.errors = stats.errors
                run.status = final_status
                run.message = message
        logger.info(
            "ingestion run %s finished status=%s rows=%s errors=%s in %ss",
            run_id, final_status, stats.rows_written, stats.errors, duration,
        )
