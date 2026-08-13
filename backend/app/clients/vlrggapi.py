"""Client for the self-hosted vlrggapi fork (enrichment data path).

This talks ONLY to a local instance (default http://127.0.0.1:3001). vlr.gg
blocks datacenter/cloud IP ranges via bot protection, so the scraper must run
on a residential connection. The public ``vlrggapi.vercel.app`` is down and is
intentionally NOT used.

This data path is best-effort enrichment: if the local instance is unreachable
(home machine off, network down), callers should catch ``VlrggApiError`` and
degrade gracefully rather than fail.

V2 response envelope: ``{"status": "success", "data": {...}}``.
"""
from __future__ import annotations

import logging
import time
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ..config import settings

logger = logging.getLogger(__name__)


class VlrggApiError(RuntimeError):
    """Raised when the local vlrggapi instance errors or is unreachable."""


class _RetryableStatus(Exception):
    """Raised for 5xx or 429 to trigger tenacity retry."""


class VlrggApiClient:
    def __init__(self, base_url: str | None = None, timeout: float = 30.0) -> None:
        self.base_url = (base_url or settings.vlrggapi_base_url).rstrip("/")
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            headers={"Accept": "application/json"},
        )

    # -- lifecycle ----------------------------------------------------------
    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "VlrggApiClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- low-level ----------------------------------------------------------
    @retry(
        retry=retry_if_exception_type(_RetryableStatus),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        reraise=True,
    )
    def _get_raw(self, path: str, params: dict[str, Any] | None = None) -> httpx.Response:
        try:
            resp = self._client.get(path, params=params)
        except httpx.RequestError as exc:
            # Connection refused / DNS / timeout => local instance likely down.
            raise VlrggApiError(
                f"Could not reach vlrggapi at {self.base_url}{path}: {exc}. "
                "Is the local instance running?"
            ) from exc
        if resp.status_code == 429:
            retry_after = 2.0
            try:
                body = resp.json()
                ra = (body.get("detail") or {}).get("retry_after")
                if ra and float(ra) > 0:
                    retry_after = float(ra)
            except Exception:
                pass
            logger.warning("429 rate-limited on %s, sleeping %.1fs", path, retry_after)
            time.sleep(retry_after)
            raise _RetryableStatus(f"429 on {path}")
        if resp.status_code >= 500:
            raise _RetryableStatus(f"{resp.status_code} on {path}")
        if resp.status_code >= 400:
            raise VlrggApiError(
                f"vlrggapi {resp.status_code} on {path}: {resp.text[:300]}"
            )
        return resp

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """Return the unwrapped ``data`` payload for V2 endpoints.

        Endpoints wrap successful responses as ``{"status": "success",
        "data": ...}``. ``/v2/health`` and non-envelope routes are returned
        as-is.
        """
        body = self._get_raw(path, params).json()
        if isinstance(body, dict) and "data" in body and "status" in body:
            if body.get("status") not in ("success", 200, "200"):
                raise VlrggApiError(f"vlrggapi non-success on {path}: {body}")
            return body["data"]
        return body

    # -- V2 endpoints -------------------------------------------------------
    def health(self) -> Any:
        return self._get("/v2/health")

    def news(self) -> Any:
        return self._get("/v2/news")

    def rankings(self, region: str) -> Any:
        return self._get("/v2/rankings", {"region": region})

    def stats(self, region: str, timespan: str = "all") -> Any:
        return self._get("/v2/stats", {"region": region, "timespan": timespan})

    def matches(self, q: str = "upcoming", **params: Any) -> Any:
        """q: upcoming | upcoming_extended | live_score | results."""
        return self._get("/v2/match", {"q": q, **params})

    def match_details(self, match_id: str | int) -> Any:
        return self._get("/v2/match/details", {"match_id": str(match_id)})

    def events(self, q: str | None = None, page: int | None = None) -> Any:
        """q: upcoming | completed | live (optional)."""
        params: dict[str, Any] = {}
        if q is not None:
            params["q"] = q
        if page is not None:
            params["page"] = page
        return self._get("/v2/events", params)

    def event_detail(self, event_id: str | int) -> Any:
        return self._get(f"/v2/event/{event_id}")

    def event_matches(self, event_id: str | int) -> Any:
        return self._get("/v2/events/matches", {"event_id": str(event_id)})

    def search(self, q: str) -> Any:
        return self._get("/v2/search", {"q": q})

    def player(self, player_id: str | int, q: str = "profile", **params: Any) -> Any:
        return self._get("/v2/player", {"id": str(player_id), "q": q, **params})

    def team(self, team_id: str | int, q: str = "profile", **params: Any) -> Any:
        """q: profile | matches | transactions | stats."""
        return self._get("/v2/team", {"id": str(team_id), "q": q, **params})
