"""vlr.gg (local vlrggapi) -> Postgres enrichment ingestion.

Walks completed events -> event matches -> match details on the LOCAL vlrggapi
instance and attaches per-map scores and per-player stats to the matching
PandaScore-sourced match rows. Reconciliation is by normalised team-name set +
date window (see ``reconcile``). Unmatched vlr matches are counted and sampled
into the run log rather than dropped silently.

This whole path is best-effort: if the local instance is unreachable the run
fails loudly (and is logged), but nothing downstream depends on it having run.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, aliased

from ..clients import VlrggApiClient, VlrggApiError
from ..db.base import session_scope
from ..db.models import Match, Team
from . import repository as repo
from .reconcile import MatchIndex, parse_listing_date
from .names import normalize_name
from .runlog import RunStats, ingestion_run

logger = logging.getLogger("ingest.vlr")

_MAX_UNMATCHED_SAMPLES = 50


def _to_int(v: Any) -> int | None:
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return None


def _to_float(v: Any) -> float | None:
    if v is None:
        return None
    t = str(v).strip().rstrip("%")
    if not t or t in {"+", "-"}:
        return None
    try:
        return float(t)
    except ValueError:
        return None


def _segments(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        return payload.get("segments") or []
    return payload or []


def _db_match_sides(session: Session, match_id: int) -> dict[str, Any] | None:
    ta, tb = aliased(Team), aliased(Team)
    row = session.execute(
        select(
            Match.team_a_id, Match.team_b_id,
            ta.normalized_name, tb.normalized_name,
        )
        .join(ta, Match.team_a_id == ta.id)
        .join(tb, Match.team_b_id == tb.id)
        .where(Match.id == match_id)
    ).first()
    if row is None:
        return None
    return {"a_id": row[0], "b_id": row[1], "a_norm": row[2], "b_norm": row[3]}


def enrich_match(
    session: Session,
    db_match_id: int,
    detail: dict[str, Any],
    vlr_match_id: str,
    player_cache: dict[tuple[int | None, str], int],
) -> int:
    """Attach vlr maps/player stats to a DB match. Returns map count written."""
    sides = _db_match_sides(session, db_match_id)
    if sides is None:
        return 0
    vlr_teams = detail.get("teams") or []
    if len(vlr_teams) != 2:
        return 0

    # Map vlr side index (0=team1, 1=team2) -> DB team id, by normalised name.
    n0 = normalize_name(vlr_teams[0].get("name"))
    if n0 == sides["a_norm"]:
        side_db_id = [sides["a_id"], sides["b_id"]]
        side_is_a = [True, False]
    else:
        side_db_id = [sides["b_id"], sides["a_id"]]
        side_is_a = [False, True]

    # Record vlr team ids on our teams (best-effort).
    for idx, vt in enumerate(vlr_teams):
        if vt.get("id"):
            repo.set_team_vlr_id(session, side_db_id[idx], str(vt["id"]))

    maps_out: list[dict[str, Any]] = []
    for order, mp in enumerate(detail.get("maps") or [], start=1):
        name = (mp.get("map_name") or "").strip()
        if not name or name.upper() == "TBD":
            continue
        score = mp.get("score") or {}
        s1, s2 = _to_int(score.get("team1")), _to_int(score.get("team2"))
        team_a_score = s1 if side_is_a[0] else s2
        team_b_score = s2 if side_is_a[0] else s1
        winner_id = None
        if s1 is not None and s2 is not None and s1 != s2:
            winner_id = side_db_id[0] if s1 > s2 else side_db_id[1]

        players_out: list[dict[str, Any]] = []
        for side_idx, key in ((0, "team1"), (1, "team2")):
            team_id = side_db_id[side_idx]
            for p in (mp.get("players") or {}).get(key, []) or []:
                pname = (p.get("name") or "").strip()
                if not pname:
                    continue
                pid = repo.get_or_create_player(session, pname, team_id, player_cache)
                agent = (p.get("agent") or "").strip() or None
                players_out.append({
                    "player_id": pid,
                    "team_id": team_id,
                    "agent": agent,
                    "kills": _to_int(p.get("kills")),
                    "deaths": _to_int(p.get("deaths")),
                    "assists": _to_int(p.get("assists")),
                    "acs": _to_float(p.get("acs")),
                    "rating": _to_float(p.get("rating")),
                    "adr": _to_float(p.get("adr")),
                })

        maps_out.append({
            "map_name": name,
            "map_order": order,
            "picked_by": (mp.get("picked_by") or "").strip() or None,
            "team_a_score": team_a_score,
            "team_b_score": team_b_score,
            "winner_id": winner_id,
            "players": players_out,
        })

    return repo.replace_match_enrichment(
        session, match_id=db_match_id, vlr_match_id=vlr_match_id, maps=maps_out
    )


def backfill(
    max_event_pages: int | None = None,
    max_events: int | None = None,
    request_delay: float = 1.0,
) -> RunStats:
    """Walk completed events and enrich matched matches with vlr data."""
    with ingestion_run(source="vlrggapi", job="backfill") as stats:
        with session_scope() as session:
            index = MatchIndex.build(session)

        matched = unmatched = 0
        player_cache: dict[tuple[int | None, str], int] = {}
        events_seen = 0

        with VlrggApiClient() as vlr:
            page = 1
            while max_event_pages is None or page <= max_event_pages:
                events = _segments(vlr.events(q="completed", page=page))
                if not events:
                    break
                if request_delay:
                    time.sleep(request_delay)
                for ev in events:
                    if max_events is not None and events_seen >= max_events:
                        break
                    events_seen += 1
                    event_id = ev.get("event_id")
                    try:
                        em = _segments(vlr.event_matches(event_id))
                    except VlrggApiError as exc:
                        stats.add_error(f"event {event_id} matches: {exc}")
                        continue
                    if request_delay:
                        time.sleep(request_delay)

                    with session_scope() as session:
                        for vm in em:
                            t1 = (vm.get("team1") or {}).get("name")
                            t2 = (vm.get("team2") or {}).get("name")
                            when = parse_listing_date(vm.get("date"))
                            db_id = index.find(t1, t2, when)
                            if db_id is None:
                                unmatched += 1
                                if unmatched <= _MAX_UNMATCHED_SAMPLES:
                                    stats.note(
                                        f"unmatched vlr {vm.get('match_id')}: "
                                        f"{t1} vs {t2} @ {when} [{ev.get('title')}]"
                                    )
                                continue
                            try:
                                detail_segs = _segments(
                                    vlr.match_details(vm.get("match_id"))
                                )
                                if not detail_segs:
                                    continue
                                # Per-match savepoint: a DB error (e.g. a vlr_id
                                # collision) rolls back just this match, not the
                                # whole event, so the backfill keeps going.
                                with session.begin_nested():
                                    n = enrich_match(
                                        session, db_id, detail_segs[0],
                                        str(vm.get("match_id")), player_cache,
                                    )
                                if n:
                                    matched += 1
                                    stats.add_rows(1)
                            except VlrggApiError as exc:
                                stats.add_error(f"detail {vm.get('match_id')}: {exc}")
                            except SQLAlchemyError as exc:
                                stats.add_error(
                                    f"enrich {vm.get('match_id')} -> match {db_id}: "
                                    f"{type(exc).__name__}"
                                )
                            if request_delay:
                                time.sleep(request_delay)
                if max_events is not None and events_seen >= max_events:
                    break
                page += 1

        stats.note(
            f"reconciliation summary: matched={matched} unmatched={unmatched} "
            f"events_scanned={events_seen}"
        )
        return stats
