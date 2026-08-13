"""Unit tests for the PandaScore client (mocked HTTP, no live token needed)."""
from __future__ import annotations

import httpx
import pytest
import respx

from backend.app.clients import PandaScoreClient, PandaScoreError

BASE = "https://api.pandascore.co"


def _client() -> PandaScoreClient:
    return PandaScoreClient(token="test-token", base_url=BASE)


@respx.mock
def test_matches_sends_bearer_and_parses():
    route = respx.get(f"{BASE}/valorant/matches/past").mock(
        return_value=httpx.Response(200, json=[{"id": 1, "name": "A vs B"}])
    )
    with _client() as ps:
        got = list(ps.matches(status="past"))

    assert got == [{"id": 1, "name": "A vs B"}]
    sent = route.calls.last.request
    assert sent.headers["Authorization"] == "Bearer test-token"
    assert sent.url.params["page[number]"] == "1"
    assert sent.url.params["sort"] == "-begin_at"


@respx.mock
def test_pagination_follows_until_short_page():
    full = [{"id": i} for i in range(100)]
    respx.get(f"{BASE}/valorant/teams").mock(
        side_effect=[
            httpx.Response(200, json=full),          # page 1: full -> keep going
            httpx.Response(200, json=[{"id": 100}]),  # page 2: short -> stop
        ]
    )
    with _client() as ps:
        got = list(ps.teams())
    assert len(got) == 101


@respx.mock
def test_retries_on_429_then_succeeds():
    respx.get(f"{BASE}/valorant/matches/upcoming").mock(
        side_effect=[
            httpx.Response(429),
            httpx.Response(200, json=[{"id": 7}]),
        ]
    )
    with _client() as ps:
        got = list(ps.matches(status="upcoming"))
    assert got == [{"id": 7}]


@respx.mock
def test_401_raises_pandascore_error():
    respx.get(f"{BASE}/valorant/matches/past").mock(
        return_value=httpx.Response(401, json={"error": "Invalid credentials"})
    )
    with _client() as ps, pytest.raises(PandaScoreError, match="401"):
        list(ps.matches(status="past"))


def test_missing_token_raises():
    with pytest.raises(PandaScoreError, match="No PandaScore token"):
        PandaScoreClient(token="", base_url=BASE)


def test_invalid_status_rejected():
    with _client() as ps, pytest.raises(ValueError):
        list(ps.matches(status="bogus"))
