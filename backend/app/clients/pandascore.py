"""PandaScore API client.

PandaScore is the *source of truth* for Valorant match schedules and results.
The free tier is a real commercial API (no scraping risk), so this path must be
able to keep the app correct on its own even when the local vlr.gg scraper is
offline.

Docs: https://developers.pandascore.co/reference
Auth: Bearer token in the Authorization header.
Pagination: ``page[number]`` (1-based) + ``page[size]`` (<= 100).
"""
from __future__ import annotations

from typing import Any, Iterator

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ..config import settings

# PandaScore free tier caps page size at 100.
MAX_PAGE_SIZE = 100
VALORANT = "valorant"


class PandaScoreError(RuntimeError):
    """Raised when the PandaScore API returns an unrecoverable error."""


class _RetryableStatus(Exception):
    """Internal marker for status codes worth retrying (429 / 5xx)."""


class PandaScoreClient:
    def __init__(
        self,
        token: str | None = None,
        base_url: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.token = settings.pandascore_token if token is None else token
        if not self.token:
            raise PandaScoreError(
                "No PandaScore token configured. Set PANDASCORE_TOKEN in .env."
            )
        self.base_url = (base_url or settings.pandascore_base_url).rstrip("/")
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/json",
            },
        )

    # -- lifecycle ----------------------------------------------------------
    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "PandaScoreClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- low-level request --------------------------------------------------
    @retry(
        retry=retry_if_exception_type(_RetryableStatus),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )
    def _get(self, path: str, params: dict[str, Any] | None = None) -> httpx.Response:
        try:
            resp = self._client.get(path, params=params)
        except httpx.RequestError as exc:
            raise PandaScoreError(f"Request to {path} failed: {exc}") from exc

        if resp.status_code == 429 or resp.status_code >= 500:
            raise _RetryableStatus(f"{resp.status_code} on {path}")
        if resp.status_code >= 400:
            raise PandaScoreError(
                f"PandaScore {resp.status_code} on {path}: {resp.text[:300]}"
            )
        return resp

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return self._get(path, params).json()

    # -- pagination ---------------------------------------------------------
    def paginate(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        page_size: int = MAX_PAGE_SIZE,
        max_pages: int | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Yield items across all pages until the API returns a short page."""
        params = dict(params or {})
        page_size = min(page_size, MAX_PAGE_SIZE)
        page = 1
        while True:
            params["page[size]"] = page_size
            params["page[number]"] = page
            batch = self._get(path, params).json()
            if not isinstance(batch, list):
                raise PandaScoreError(
                    f"Expected a list from {path}, got {type(batch).__name__}"
                )
            yield from batch
            if len(batch) < page_size:
                return
            page += 1
            if max_pages is not None and page > max_pages:
                return

    # -- Valorant endpoints -------------------------------------------------
    def matches(
        self,
        status: str = "past",
        *,
        sort: str = "-begin_at",
        extra_params: dict[str, Any] | None = None,
        page_size: int = MAX_PAGE_SIZE,
        max_pages: int | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Iterate Valorant matches.

        ``status`` is one of ``past``, ``running``, ``upcoming``. PandaScore
        exposes these as dedicated sub-paths under ``/valorant/matches``.
        """
        if status not in {"past", "running", "upcoming"}:
            raise ValueError("status must be past, running, or upcoming")
        params: dict[str, Any] = {"sort": sort}
        if extra_params:
            params.update(extra_params)
        yield from self.paginate(
            f"/{VALORANT}/matches/{status}",
            params=params,
            page_size=page_size,
            max_pages=max_pages,
        )

    def teams(self, **kw: Any) -> Iterator[dict[str, Any]]:
        yield from self.paginate(f"/{VALORANT}/teams", **kw)

    def players(self, **kw: Any) -> Iterator[dict[str, Any]]:
        yield from self.paginate(f"/{VALORANT}/players", **kw)

    def tournaments(self, **kw: Any) -> Iterator[dict[str, Any]]:
        yield from self.paginate(f"/{VALORANT}/tournaments", **kw)

    def series(self, **kw: Any) -> Iterator[dict[str, Any]]:
        yield from self.paginate(f"/{VALORANT}/series", **kw)

    def leagues(self, **kw: Any) -> Iterator[dict[str, Any]]:
        yield from self.paginate(f"/{VALORANT}/leagues", **kw)
