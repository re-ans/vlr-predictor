"""Smoke-check the PandaScore client against the live API.

Usage:
    python -m backend.scripts.check_pandascore

Requires PANDASCORE_TOKEN in .env. Prints a short summary of real matches so
you can confirm the token works and data is flowing before building on top.
"""
from __future__ import annotations

import itertools
import sys

from backend.app.clients import PandaScoreClient, PandaScoreError


def main() -> int:
    try:
        with PandaScoreClient() as ps:
            print("== PandaScore: 5 most recent finished Valorant matches ==")
            past = list(itertools.islice(ps.matches(status="past"), 5))
            if not past:
                print("  (no matches returned)")
            for m in past:
                opp = m.get("opponents", [])
                names = " vs ".join(
                    o.get("opponent", {}).get("name", "?") for o in opp
                ) or m.get("name", "?")
                winner = (m.get("winner") or {}).get("name", "?")
                print(
                    f"  [{m.get('id')}] {names} "
                    f"({m.get('begin_at')}) -> winner: {winner}"
                )

            print("\n== PandaScore: 5 upcoming Valorant matches ==")
            upcoming = list(
                itertools.islice(ps.matches(status="upcoming", sort="begin_at"), 5)
            )
            if not upcoming:
                print("  (no upcoming matches returned)")
            for m in upcoming:
                opp = m.get("opponents", [])
                names = " vs ".join(
                    o.get("opponent", {}).get("name", "?") for o in opp
                ) or m.get("name", "?")
                print(f"  [{m.get('id')}] {names} @ {m.get('begin_at')}")

        print("\nOK: PandaScore token works and returned real data.")
        return 0
    except PandaScoreError as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
