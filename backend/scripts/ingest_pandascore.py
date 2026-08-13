"""CLI for the PandaScore ingestion path.

Examples:
    # Bounded backfill (first 2 pages of past matches) -- good for a smoke test:
    python -m backend.scripts.ingest_pandascore backfill --max-pages 2

    # Full historical backfill since a date:
    python -m backend.scripts.ingest_pandascore backfill --since 2023-01-01

    # Scheduled sync (upcoming + running + recent results):
    python -m backend.scripts.ingest_pandascore sync
"""
from __future__ import annotations

import argparse
import logging
import sys

from backend.app.ingest import pandascore_ingest as pi


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    parser = argparse.ArgumentParser(description="PandaScore -> Postgres ingestion")
    sub = parser.add_subparsers(dest="command", required=True)

    p_back = sub.add_parser("backfill", help="backfill historical past matches")
    p_back.add_argument("--max-pages", type=int, default=None)
    p_back.add_argument("--since", type=str, default=None, help="ISO date, e.g. 2023-01-01")

    p_sync = sub.add_parser("sync", help="sync upcoming/running/recent matches")
    p_sync.add_argument("--max-pages", type=int, default=3)

    args = parser.parse_args(argv)

    if args.command == "backfill":
        stats = pi.backfill(max_pages=args.max_pages, since=args.since)
    else:
        stats = pi.sync(max_pages=args.max_pages)

    print(f"\nDone: rows_written={stats.rows_written} errors={stats.errors}")
    return 1 if stats.errors else 0


if __name__ == "__main__":
    sys.exit(main())
