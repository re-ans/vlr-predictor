"""PandaScore -> Postgres ingestion (source of truth for schedules/results).

This path is self-sufficient: it populates teams, events and matches (with
scores/winners) entirely from PandaScore, so the app stays correct even when
the vlr.gg enrichment path is offline.

Both entry points are idempotent (upsert on provider id):
* ``backfill`` walks historical ``/valorant/matches/past``.
* ``sync`` refreshes ``upcoming`` + ``running`` + recently ``past`` matches.
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime, timezone
from typing import Any

from ..clients import PandaScoreClient
from ..db.base import session_scope
from . import repository as repo
from .leagues import classify_league
from .runlog import RunStats, ingestion_run

logger = logging.getLogger("ingest.pandascore")

STATUS_MAP = {
    "not_started": "scheduled",
    "running": "running",
    "finished": "finished",
    "canceled": "canceled",
    "postponed": "postponed",
}

_MONEY = re.compile(r"[\d.]+")


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _parse_date(value: str | None) -> date | None:
    dt = _parse_dt(value)
    return dt.date() if dt else None


def _parse_money(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    m = _MONEY.search(str(value).replace(",", ""))
    return float(m.group()) if m else None


def _event_fields(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Map a match's serie/tournament/league into an event row (keyed by serie)."""
    serie = raw.get("serie") or {}
    tournament = raw.get("tournament") or {}
    league = raw.get("league") or {}

    pandascore_id = raw.get("serie_id") or raw.get("tournament_id")
    if not pandascore_id:
        return None

    name = (
        serie.get("full_name")
        or serie.get("name")
        or tournament.get("name")
        or league.get("name")
        or "Unknown event"
    )
    tier = tournament.get("tier")
    region = tournament.get("region")
    return {
        "pandascore_id": pandascore_id,
        "name": name,
        "tier": tier,
        "category": classify_league(name, tier, region),
        "region": region,
        "start_date": _parse_date(serie.get("begin_at") or tournament.get("begin_at")),
        "end_date": _parse_date(serie.get("end_at") or tournament.get("end_at")),
        "prize_pool": _parse_money(tournament.get("prizepool")),
    }


def _valid_opponents(raw: dict[str, Any]) -> list[dict[str, Any]] | None:
    opponents = [
        o.get("opponent")
        for o in (raw.get("opponents") or [])
        if o.get("opponent") and o["opponent"].get("id")
    ]
    return opponents if len(opponents) == 2 else None


def parse_match(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Flatten one PandaScore match into intermediate dicts, or None to skip.

    Returns ``{"teams": {pid: {..}}, "event": {..}|None, "match": {..}}`` where
    the match still references teams/event by *pandascore* id; those are resolved
    to surrogate ids during bulk load.
    """
    opponents = _valid_opponents(raw)
    if opponents is None:
        return None

    teams = {
        opp["id"]: {
            "name": opp.get("name") or f"team-{opp['id']}",
            "acronym": opp.get("acronym"),
            "country": opp.get("location"),
            "image_url": opp.get("image_url"),
        }
        for opp in opponents
    }
    team_a_pid, team_b_pid = opponents[0]["id"], opponents[1]["id"]

    scores = {r.get("team_id"): r.get("score") for r in (raw.get("results") or [])}
    winner_pid = raw.get("winner_id")

    return {
        "teams": teams,
        "event": _event_fields(raw),
        "match": {
            "pandascore_id": raw.get("id"),
            "status": STATUS_MAP.get(raw.get("status", ""), "scheduled"),
            "team_a_pid": team_a_pid,
            "team_b_pid": team_b_pid,
            "winner_pid": winner_pid,
            "event_pid": (raw.get("serie_id") or raw.get("tournament_id")),
            "match_date": _parse_dt(
                raw.get("begin_at")
                or raw.get("scheduled_at")
                or raw.get("original_scheduled_at")
            ),
            "best_of": raw.get("number_of_games"),
            "score_a": scores.get(team_a_pid),
            "score_b": scores.get(team_b_pid),
            "forfeit": bool(raw.get("forfeit", False)),
        },
    }


def _bulk_load(session, parsed: list[dict[str, Any]], stats: RunStats) -> None:
    """Resolve pandascore ids -> surrogate ids and bulk upsert a batch."""
    teams: dict[int, dict[str, Any]] = {}
    events: dict[int, dict[str, Any]] = {}
    for p in parsed:
        teams.update(p["teams"])
        if p["event"]:
            events[p["event"]["pandascore_id"]] = p["event"]

    team_map = repo.bulk_upsert_teams(session, teams)
    event_map = repo.bulk_upsert_events(session, events)

    match_rows: list[dict[str, Any]] = []
    seen: set[int] = set()
    for p in parsed:
        m = p["match"]
        pid = m["pandascore_id"]
        if pid in seen:  # de-dupe within batch (upcoming/past overlap)
            continue
        seen.add(pid)
        a_pid, b_pid, w_pid = m["team_a_pid"], m["team_b_pid"], m["winner_pid"]
        winner_id = None
        if w_pid == a_pid:
            winner_id = team_map.get(a_pid)
        elif w_pid == b_pid:
            winner_id = team_map.get(b_pid)
        match_rows.append({
            "pandascore_id": pid,
            "status": m["status"],
            "event_id": event_map.get(m["event_pid"]),
            "team_a_id": team_map.get(a_pid),
            "team_b_id": team_map.get(b_pid),
            "winner_id": winner_id,
            "match_date": m["match_date"],
            "best_of": m["best_of"],
            "score_a": m["score_a"],
            "score_b": m["score_b"],
            "forfeit": m["forfeit"],
        })

    written = repo.bulk_upsert_matches(session, match_rows)
    stats.add_rows(written)


def _run(job: str, statuses: list[str], *, sort: str, max_pages: int | None,
         extra_params: dict[str, Any] | None = None, batch_size: int = 1000) -> RunStats:
    """Collect matches from the API and bulk-load them in batches (few DB
    round-trips regardless of match count)."""
    with ingestion_run(source="pandascore", job=job) as stats:
        with PandaScoreClient() as ps:
            batch: list[dict[str, Any]] = []
            for status in statuses:
                for raw in ps.matches(
                    status=status, sort=sort, max_pages=max_pages,
                    extra_params=extra_params,
                ):
                    parsed = parse_match(raw)
                    if parsed is None:
                        stats.note(f"skip match {raw.get('id')}: not two known teams (TBD?)")
                        continue
                    batch.append(parsed)
                    if len(batch) >= batch_size:
                        with session_scope() as session:
                            _bulk_load(session, batch, stats)
                        batch = []
            if batch:
                with session_scope() as session:
                    _bulk_load(session, batch, stats)
        return stats


def backfill(max_pages: int | None = None, since: str | None = None) -> RunStats:
    """Backfill historical finished matches (oldest processed first is fine;
    upsert makes ordering irrelevant). ``since`` is an ISO date string."""
    extra = None
    if since:
        extra = {"range[begin_at]": f"{since}T00:00:00Z,{datetime.now(timezone.utc):%Y-%m-%dT%H:%M:%SZ}"}
    return _run("backfill", ["past"], sort="-begin_at", max_pages=max_pages,
                extra_params=extra)


def sync(max_pages: int | None = 3) -> RunStats:
    """Refresh upcoming + running matches and recently finished results."""
    stats_all = _run(
        "sync", ["upcoming", "running"], sort="begin_at", max_pages=max_pages
    )
    # Recent results: most-recent-first, bounded.
    _run("sync-results", ["past"], sort="-begin_at", max_pages=max_pages)
    return stats_all
