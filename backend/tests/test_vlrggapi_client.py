"""Unit tests for the vlrggapi client (mocked HTTP, no live instance needed)."""
from __future__ import annotations

import httpx
import pytest
import respx

from backend.app.clients import VlrggApiClient, VlrggApiError

BASE = "http://127.0.0.1:3001"


def _client() -> VlrggApiClient:
    return VlrggApiClient(base_url=BASE)


@respx.mock
def test_v2_envelope_is_unwrapped():
    respx.get(f"{BASE}/v2/news").mock(
        return_value=httpx.Response(
            200,
            json={"status": "success", "data": {"segments": [{"title": "Hi"}]}},
        )
    )
    with _client() as vlr:
        data = vlr.news()
    assert data == {"segments": [{"title": "Hi"}]}


@respx.mock
def test_health_passthrough():
    respx.get(f"{BASE}/v2/health").mock(
        return_value=httpx.Response(200, json={"status": "ok"})
    )
    with _client() as vlr:
        assert vlr.health() == {"status": "ok"}


@respx.mock
def test_match_details_sends_match_id():
    route = respx.get(f"{BASE}/v2/match/details").mock(
        return_value=httpx.Response(
            200, json={"status": "success", "data": {"match_id": "595657"}}
        )
    )
    with _client() as vlr:
        vlr.match_details(595657)
    assert route.calls.last.request.url.params["match_id"] == "595657"


@respx.mock
def test_connection_error_becomes_vlrggapi_error():
    respx.get(f"{BASE}/v2/health").mock(side_effect=httpx.ConnectError("refused"))
    with _client() as vlr, pytest.raises(VlrggApiError, match="Could not reach"):
        vlr.health()


@respx.mock
def test_retries_on_500_then_succeeds():
    respx.get(f"{BASE}/v2/rankings").mock(
        side_effect=[
            httpx.Response(502),
            httpx.Response(200, json={"status": "success", "data": {"segments": []}}),
        ]
    )
    with _client() as vlr:
        assert vlr.rankings("na") == {"segments": []}
