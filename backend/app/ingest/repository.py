"""Idempotent upsert helpers backed by Postgres ``INSERT ... ON CONFLICT``.

All PandaScore ingestion goes through these so re-running a backfill or sync
updates existing rows instead of duplicating them. Keys are the provider IDs
(``pandascore_id`` / ``vlr_id``), never the surrogate PK.

Fields owned by other subsystems are intentionally *not* overwritten here:
* ``teams.current_rating`` is maintained by the Elo engine (Phase 4).
* ``matches.enriched`` / ``matches.vlr_id`` are maintained by the vlr.gg path.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from sqlalchemy import delete, select, update

from ..db.models import Event, Match, MatchMap, MatchPlayerStats, Player, Team
from .names import normalize_name


def _upsert_returning_id(
    session: Session,
    model: Any,
    values: dict[str, Any],
    conflict_col: str,
    update_cols: list[str],
) -> int:
    """Generic single-row upsert on a unique column, returning the surrogate id."""
    stmt = pg_insert(model).values(**values)
    set_ = {c: stmt.excluded[c] for c in update_cols}
    set_["updated_at"] = func.now()
    stmt = stmt.on_conflict_do_update(
        index_elements=[conflict_col], set_=set_
    ).returning(model.id)
    return session.execute(stmt).scalar_one()


def upsert_team(session: Session, *, pandascore_id: int, name: str, **fields: Any) -> int:
    values = {
        "pandascore_id": pandascore_id,
        "name": name,
        "normalized_name": normalize_name(name),
        "acronym": fields.get("acronym"),
        "region": fields.get("region"),
        "country": fields.get("country"),
        "image_url": fields.get("image_url"),
    }
    return _upsert_returning_id(
        session,
        Team,
        values,
        "pandascore_id",
        ["name", "normalized_name", "acronym", "region", "country", "image_url"],
    )


def upsert_event(session: Session, *, pandascore_id: int, name: str, **fields: Any) -> int:
    values = {
        "pandascore_id": pandascore_id,
        "name": name,
        "tier": fields.get("tier"),
        "region": fields.get("region"),
        "start_date": fields.get("start_date"),
        "end_date": fields.get("end_date"),
        "prize_pool": fields.get("prize_pool"),
    }
    return _upsert_returning_id(
        session,
        Event,
        values,
        "pandascore_id",
        ["name", "tier", "region", "start_date", "end_date", "prize_pool"],
    )


def upsert_match(session: Session, *, pandascore_id: int, status: str, **fields: Any) -> int:
    values = {
        "pandascore_id": pandascore_id,
        "status": status,
        "event_id": fields.get("event_id"),
        "team_a_id": fields.get("team_a_id"),
        "team_b_id": fields.get("team_b_id"),
        "winner_id": fields.get("winner_id"),
        "match_date": fields.get("match_date"),
        "best_of": fields.get("best_of"),
        "score_a": fields.get("score_a"),
        "score_b": fields.get("score_b"),
    }
    return _upsert_returning_id(
        session,
        Match,
        values,
        "pandascore_id",
        [
            "status",
            "event_id",
            "team_a_id",
            "team_b_id",
            "winner_id",
            "match_date",
            "best_of",
            "score_a",
            "score_b",
        ],
    )


def team_id_by_pandascore(session: Session, pandascore_id: int | None) -> int | None:
    if pandascore_id is None:
        return None
    return session.execute(
        Team.__table__.select().with_only_columns(Team.id).where(
            Team.pandascore_id == pandascore_id
        )
    ).scalar_one_or_none()


# ---------------------------------------------------------------------------
# Set-based bulk upserts (used by the backfill/sync for throughput).
# Each returns a {pandascore_id: surrogate_id} map. Inputs MUST be de-duplicated
# on pandascore_id (Postgres rejects a row hitting the same conflict twice).
# ---------------------------------------------------------------------------

_CHUNK = 500


def _chunks(rows: list[dict[str, Any]], n: int = _CHUNK):
    for i in range(0, len(rows), n):
        yield rows[i : i + n]


def _bulk_upsert(
    session: Session,
    model: Any,
    rows: list[dict[str, Any]],
    update_cols: list[str],
) -> dict[int, int]:
    id_map: dict[int, int] = {}
    for chunk in _chunks(rows):
        stmt = pg_insert(model).values(chunk)
        set_ = {c: stmt.excluded[c] for c in update_cols}
        set_["updated_at"] = func.now()
        stmt = stmt.on_conflict_do_update(
            index_elements=["pandascore_id"], set_=set_
        ).returning(model.pandascore_id, model.id)
        for pid, sid in session.execute(stmt).all():
            id_map[pid] = sid
    return id_map


def bulk_upsert_teams(session: Session, teams: dict[int, dict[str, Any]]) -> dict[int, int]:
    rows = [
        {
            "pandascore_id": pid,
            "name": t["name"],
            "normalized_name": normalize_name(t["name"]),
            "acronym": t.get("acronym"),
            "region": t.get("region"),
            "country": t.get("country"),
            "image_url": t.get("image_url"),
        }
        for pid, t in teams.items()
    ]
    if not rows:
        return {}
    return _bulk_upsert(
        session, Team, rows,
        ["name", "normalized_name", "acronym", "region", "country", "image_url"],
    )


def bulk_upsert_events(session: Session, events: dict[int, dict[str, Any]]) -> dict[int, int]:
    rows = list(events.values())
    if not rows:
        return {}
    return _bulk_upsert(
        session, Event, rows,
        ["name", "tier", "category", "region", "start_date", "end_date", "prize_pool"],
    )


def bulk_upsert_matches(session: Session, matches: list[dict[str, Any]]) -> int:
    if not matches:
        return 0
    count = 0
    for chunk in _chunks(matches):
        stmt = pg_insert(Match).values(chunk)
        set_ = {
            c: stmt.excluded[c]
            for c in [
                "status", "event_id", "team_a_id", "team_b_id", "winner_id",
                "match_date", "best_of", "score_a", "score_b", "forfeit",
            ]
        }
        set_["updated_at"] = func.now()
        stmt = stmt.on_conflict_do_update(index_elements=["pandascore_id"], set_=set_)
        session.execute(stmt)
        count += len(chunk)
    return count


# ---------------------------------------------------------------------------
# vlr.gg enrichment writes (Phase 3c). All enrichment is best-effort and lives
# under an existing (PandaScore-sourced) match row.
# ---------------------------------------------------------------------------


def get_or_create_player(
    session: Session,
    name: str,
    team_id: int | None,
    cache: dict[tuple[int | None, str], int],
) -> int:
    key = (team_id, name)
    if key in cache:
        return cache[key]
    pid = session.execute(
        select(Player.id).where(Player.name == name, Player.team_id == team_id)
    ).scalar_one_or_none()
    if pid is None:
        pid = session.execute(
            pg_insert(Player)
            .values(name=name, team_id=team_id)
            .returning(Player.id)
        ).scalar_one()
    cache[key] = pid
    return pid


def replace_match_enrichment(
    session: Session,
    *,
    match_id: int,
    vlr_match_id: str,
    maps: list[dict[str, Any]],
) -> int:
    """Replace all vlr-sourced maps/player-stats for a match, idempotently.

    ``maps`` is a list of dicts:
        {map_name, map_order, picked_by, team_a_score, team_b_score,
         winner_id, players: [{player_id, team_id, agent, kills, deaths,
         assists, acs, rating, adr}, ...]}
    Returns the number of map rows written.
    """
    # Clear existing enrichment (cascade removes player stats).
    session.execute(delete(MatchMap).where(MatchMap.match_id == match_id))

    for m in maps:
        map_id = session.execute(
            pg_insert(MatchMap)
            .values(
                match_id=match_id,
                map_name=m.get("map_name"),
                map_order=m.get("map_order"),
                picked_by=m.get("picked_by"),
                team_a_score=m.get("team_a_score"),
                team_b_score=m.get("team_b_score"),
                winner_id=m.get("winner_id"),
            )
            .returning(MatchMap.id)
        ).scalar_one()
        stat_rows = [
            {
                "match_map_id": map_id,
                "player_id": p.get("player_id"),
                "team_id": p.get("team_id"),
                "agent": p.get("agent"),
                "kills": p.get("kills"),
                "deaths": p.get("deaths"),
                "assists": p.get("assists"),
                "acs": p.get("acs"),
                "rating": p.get("rating"),
                "adr": p.get("adr"),
            }
            for p in m.get("players", [])
        ]
        if stat_rows:
            session.execute(pg_insert(MatchPlayerStats).values(stat_rows))

    session.execute(
        update(Match)
        .where(Match.id == match_id)
        .values(enriched=True, vlr_id=str(vlr_match_id), updated_at=func.now())
    )
    return len(maps)


def set_team_vlr_id(session: Session, team_id: int, vlr_id: str) -> None:
    """Best-effort: record a team's vlr id (skip if already taken by another)."""
    exists = session.execute(
        select(Team.id).where(Team.vlr_id == vlr_id)
    ).scalar_one_or_none()
    if exists is None:
        session.execute(
            update(Team).where(Team.id == team_id).values(vlr_id=vlr_id)
        )
