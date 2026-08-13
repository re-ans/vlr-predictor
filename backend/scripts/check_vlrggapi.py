"""Smoke-check the local vlrggapi fork.

Usage:
    python -m backend.scripts.check_vlrggapi

Confirms /v2/health and /v2/news return valid data from your home network.
Run this on the machine hosting the vlrggapi Docker container (or one on the
same LAN), NOT from the cloud sandbox.
"""
from __future__ import annotations

import sys

from backend.app.clients import VlrggApiClient, VlrggApiError


def main() -> int:
    try:
        with VlrggApiClient() as vlr:
            print(f"== vlrggapi @ {vlr.base_url} ==")

            health = vlr.health()
            print(f"/v2/health -> {health}")

            news = vlr.news()
            segments = news.get("segments", []) if isinstance(news, dict) else []
            print(f"/v2/news -> {len(segments)} articles")
            for a in segments[:3]:
                print(f"  - {a.get('title')} ({a.get('date')})")

        print("\nOK: local vlrggapi is reachable and returning data.")
        return 0
    except VlrggApiError as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        print(
            "\nHint: start the fork locally (see README > Self-hosting vlrggapi) "
            "and confirm VLRGGAPI_BASE_URL points at it.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
