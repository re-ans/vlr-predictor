"""CLI for the vlr.gg enrichment ingestion (LOCAL vlrggapi only).

Run this on the machine hosting vlrggapi (or on the same LAN). It reads from
http://127.0.0.1:3001 and writes enrichment into the cloud Postgres.

Examples:
    # Bounded smoke run over the most recent completed events:
    python -m backend.scripts.ingest_vlr backfill --max-events 40

    # Full-ish backfill (be mindful of the 600 req/min vlrggapi limit):
    python -m backend.scripts.ingest_vlr backfill --request-delay 0.1
"""
from __future__ import annotations

import argparse
import logging
import sys

from backend.app.ingest import vlr_ingest as vi


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    parser = argparse.ArgumentParser(description="vlrggapi -> Postgres enrichment")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("backfill", help="enrich matches from completed events")
    p.add_argument("--max-event-pages", type=int, default=None)
    p.add_argument("--max-events", type=int, default=None)
    p.add_argument("--request-delay", type=float, default=1.0,
                    help="seconds between API calls (default 1.0)")

    args = parser.parse_args(argv)
    stats = vi.backfill(
        max_event_pages=args.max_event_pages,
        max_events=args.max_events,
        request_delay=args.request_delay,
    )
    print(f"\nDone: rows_written={stats.rows_written} errors={stats.errors}")
    return 1 if stats.errors else 0


if __name__ == "__main__":
    sys.exit(main())
