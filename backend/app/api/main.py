"""FastAPI application: prediction API + match/team data endpoints."""
from __future__ import annotations

import logging
import time
import threading
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select, text
from sqlalchemy.orm import aliased

from ..db.base import session_scope
from ..db.models import Event, Match, Team
from datetime import datetime, timedelta, timezone
from ..features.model import ModelBundle, load_model
from ..ingest.leagues import CATEGORY_LABELS
from .predict import compute_live_features, warm_cache
from .schemas import (
    CategoryListResponse,
    HealthResponse,
    LeaderboardEntry,
    LeaderboardResponse,
    MatchListResponse,
    MatchOut,
    PredictionRequest,
    PredictionResponse,
    TeamListResponse,
    TeamOut,
)

logger = logging.getLogger("api")

_model: ModelBundle | None = None

_VLR_MATCH = "https://www.vlr.gg/{vlr_id}"
_VLR_TEAM = "https://www.vlr.gg/team/{vlr_id}"
_VLR_SEARCH = "https://www.vlr.gg/search/?q={q}&type={type}"


def _vlr_match_url(vlr_id: str | None, team_a: str | None = None, team_b: str | None = None) -> str | None:
    if vlr_id:
        return _VLR_MATCH.format(vlr_id=vlr_id)
    # Fallback: search vlr.gg for the matchup
    if team_a and team_b:
        from urllib.parse import quote
        return _VLR_SEARCH.format(q=quote(f"{team_a} vs {team_b}"), type="matches")
    return None


def _vlr_team_url(vlr_id: str | None, name: str | None = None) -> str | None:
    if vlr_id:
        return _VLR_TEAM.format(vlr_id=vlr_id)
    if name:
        from urllib.parse import quote
        return _VLR_SEARCH.format(q=quote(name), type="teams")
    return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _model
    try:
        _model = load_model()
        logger.info("Model loaded successfully")
    except Exception as exc:
        logger.warning("Could not load model: %s", exc)
        _model = None
    warm_cache()
    yield


app = FastAPI(
    title="VLR Predictor API",
    description="Valorant match winner prediction service",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Helpers — single-query match loading with JOINs
# ---------------------------------------------------------------------------

TeamA = aliased(Team, name="ta")
TeamB = aliased(Team, name="tb")
TeamW = aliased(Team, name="tw")


def _match_query():
    """Base query that joins match → event, team_a, team_b, winner."""
    return (
        select(
            Match,
            Event.name.label("event_name"),
            Event.category.label("event_category"),
            TeamA.name.label("ta_name"),
            TeamA.vlr_id.label("ta_vlr"),
            TeamA.image_url.label("ta_image"),
            TeamA.current_rating.label("ta_elo"),
            TeamB.name.label("tb_name"),
            TeamB.vlr_id.label("tb_vlr"),
            TeamB.image_url.label("tb_image"),
            TeamB.current_rating.label("tb_elo"),
            TeamW.name.label("tw_name"),
        )
        .outerjoin(Event, Match.event_id == Event.id)
        .outerjoin(TeamA, Match.team_a_id == TeamA.id)
        .outerjoin(TeamB, Match.team_b_id == TeamB.id)
        .outerjoin(TeamW, Match.winner_id == TeamW.id)
    )


def _row_to_match(row, prediction=None) -> MatchOut:
    m = row[0]  # Match ORM object
    return MatchOut(
        id=m.id,
        event_name=row.event_name,
        event_category=row.event_category,
        team_a_name=row.ta_name,
        team_b_name=row.tb_name,
        team_a_id=m.team_a_id,
        team_b_id=m.team_b_id,
        team_a_image=row.ta_image,
        team_b_image=row.tb_image,
        winner_name=row.tw_name,
        winner_id=m.winner_id,
        match_date=m.match_date,
        best_of=m.best_of,
        status=m.status,
        score_a=m.score_a,
        score_b=m.score_b,
        enriched=m.enriched,
        vlr_url=_vlr_match_url(m.vlr_id, row.ta_name, row.tb_name),
        team_a_vlr_url=_vlr_team_url(row.ta_vlr, row.ta_name),
        team_b_vlr_url=_vlr_team_url(row.tb_vlr, row.tb_name),
        prediction=prediction,
    )


def _apply_event_filters(q, count_q, category: str | None, region: str | None):
    """Filter match queries by event category/region via JOIN."""
    if not category and not region:
        return q, count_q
    need_join = True
    if category:
        q = q.where(Event.category == category)
    if region:
        q = q.where(Event.region == region)
    # count_q doesn't have Event joined yet
    if need_join:
        count_q = count_q.join(Event, Match.event_id == Event.id)
    if category:
        count_q = count_q.where(Event.category == category)
    if region:
        count_q = count_q.where(Event.region == region)
    return q, count_q


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/api/health", response_model=HealthResponse)
def health():
    with session_scope() as session:
        match_count = session.execute(
            select(func.count()).select_from(Match)
        ).scalar() or 0
        team_count = session.execute(
            select(func.count()).select_from(Team)
        ).scalar() or 0
    return HealthResponse(
        status="ok",
        model_loaded=_model is not None,
        match_count=match_count,
        team_count=team_count,
    )


# ---------------------------------------------------------------------------
# Refresh (sync latest results from PandaScore)
# ---------------------------------------------------------------------------

_SYNC_COOLDOWN = 120  # seconds between syncs
_last_sync: float = 0.0
_sync_lock = threading.Lock()


@app.post("/api/refresh")
def refresh_matches():
    """Sync upcoming/running/recently-finished matches from PandaScore.

    Rate-limited to at most once every 2 minutes to avoid hammering the API.
    Returns immediately if a sync is already in progress or was done recently.
    """
    global _last_sync

    now = time.time()
    if now - _last_sync < _SYNC_COOLDOWN:
        remaining = int(_SYNC_COOLDOWN - (now - _last_sync))
        return {"synced": False, "message": f"Cooldown: retry in {remaining}s"}

    if not _sync_lock.acquire(blocking=False):
        return {"synced": False, "message": "Sync already in progress"}

    try:
        _last_sync = time.time()
        from ..ingest.pandascore_ingest import sync
        stats = sync(max_pages=2)

        # Resolve stale scheduled matches that fell outside the paginated
        # ``past`` window by fetching their real results by id.
        resolved = _resolve_stale_scheduled()

        # Rebuild the Elo/stats cache so predictions reflect new results
        warm_cache()
        return {
            "synced": True,
            "rows_updated": stats.rows_written + resolved,
            "errors": stats.errors,
        }
    except Exception as exc:
        logger.error("Refresh failed: %s", exc)
        return {"synced": False, "message": str(exc)}
    finally:
        _sync_lock.release()


def _resolve_stale_scheduled(hours: int = 2) -> int:
    """Fetch real results for scheduled matches whose start time passed >``hours``
    ago (PandaScore has likely finished them, but they're beyond the recent
    ``past`` pagination window). Returns the number of rows updated.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    with session_scope() as session:
        rows = session.execute(
            select(Match.pandascore_id).where(
                Match.status == "scheduled",
                Match.match_date < cutoff,
                Match.pandascore_id.isnot(None),
            )
        ).scalars().all()
    ids = [int(x) for x in rows]
    if not ids:
        return 0
    from ..ingest.pandascore_ingest import sync_by_ids
    stats = sync_by_ids(ids)
    logger.info("Resolved %s stale scheduled matches by id", stats.rows_written)
    return stats.rows_written


# ---------------------------------------------------------------------------
# Categories (for UI filter dropdowns)
# ---------------------------------------------------------------------------

@app.get("/api/categories", response_model=CategoryListResponse)
def list_categories():
    return CategoryListResponse(
        categories=[{"value": k, "label": v} for k, v in CATEGORY_LABELS.items()]
    )


# ---------------------------------------------------------------------------
# Prediction
# ---------------------------------------------------------------------------

@app.post("/api/predict", response_model=PredictionResponse)
def predict(req: PredictionRequest):
    if _model is None:
        raise HTTPException(503, "Model not loaded. Train one first.")

    try:
        features = compute_live_features(req.team_a_id, req.team_b_id, req.best_of)
    except ValueError as exc:
        raise HTTPException(404, str(exc))

    pred = _model.predict(features)

    with session_scope() as session:
        ta = session.get(Team, req.team_a_id)
        tb = session.get(Team, req.team_b_id)
        team_a_name = ta.name if ta else f"Team {req.team_a_id}"
        team_b_name = tb.name if tb else f"Team {req.team_b_id}"

    winner_name = team_a_name if pred.predicted_winner == "team_a" else team_b_name

    return PredictionResponse(
        team_a_id=req.team_a_id,
        team_b_id=req.team_b_id,
        team_a_name=team_a_name,
        team_b_name=team_b_name,
        team_a_win_prob=pred.team_a_win_prob,
        team_b_win_prob=pred.team_b_win_prob,
        predicted_winner=winner_name,
        confidence=pred.confidence,
        features=features,
    )


# ---------------------------------------------------------------------------
# Matches
# ---------------------------------------------------------------------------

@app.get("/api/matches", response_model=MatchListResponse)
def list_matches(
    status: str | None = Query(None, description="Filter by status"),
    category: str | None = Query(None, description="Filter by league category"),
    region: str | None = Query(None, description="Filter by event region"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    with session_scope() as session:
        q = _match_query().order_by(Match.match_date.desc().nullslast())
        count_q = select(func.count()).select_from(Match)

        if status:
            q = q.where(Match.status == status)
            count_q = count_q.where(Match.status == status)

        q, count_q = _apply_event_filters(q, count_q, category, region)

        total = session.execute(count_q).scalar() or 0
        rows = session.execute(
            q.offset((page - 1) * page_size).limit(page_size)
        ).all()

        matches = [_row_to_match(r) for r in rows]

    return MatchListResponse(
        matches=matches, total=total, page=page, page_size=page_size
    )


@app.get("/api/matches/{match_id}", response_model=MatchOut)
def get_match(match_id: int):
    with session_scope() as session:
        row = session.execute(
            _match_query().where(Match.id == match_id)
        ).first()
        if row is None:
            raise HTTPException(404, f"Match {match_id} not found")

        m = row[0]
        prediction = None
        if _model and m.team_a_id and m.team_b_id:
            try:
                features = compute_live_features(
                    m.team_a_id, m.team_b_id, m.best_of or 3
                )
                pred = _model.predict(features)
                prediction = PredictionResponse(
                    team_a_id=m.team_a_id,
                    team_b_id=m.team_b_id,
                    team_a_name=row.ta_name or "",
                    team_b_name=row.tb_name or "",
                    team_a_win_prob=pred.team_a_win_prob,
                    team_b_win_prob=pred.team_b_win_prob,
                    predicted_winner=(
                        (row.ta_name or "") if pred.predicted_winner == "team_a"
                        else (row.tb_name or "")
                    ),
                    confidence=pred.confidence,
                    features=features,
                )
            except Exception as exc:
                logger.debug("Prediction failed for match %d: %s", m.id, exc)

        return _row_to_match(row, prediction)


# ---------------------------------------------------------------------------
# Teams
# ---------------------------------------------------------------------------

@app.get("/api/teams", response_model=TeamListResponse)
def list_teams(
    search: str | None = Query(None, description="Search by name"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    with session_scope() as session:
        q = select(Team).order_by(Team.current_rating.desc())
        count_q = select(func.count()).select_from(Team)

        if search:
            q = q.where(Team.name.ilike(f"%{search}%"))
            count_q = count_q.where(Team.name.ilike(f"%{search}%"))

        total = session.execute(count_q).scalar() or 0
        rows = session.execute(
            q.offset((page - 1) * page_size).limit(page_size)
        ).scalars().all()

        teams = [
            TeamOut(
                id=t.id,
                name=t.name,
                acronym=t.acronym,
                region=t.region,
                country=t.country,
                image_url=t.image_url,
                current_rating=float(t.current_rating),
                vlr_url=_vlr_team_url(t.vlr_id, t.name),
            )
            for t in rows
        ]

    return TeamListResponse(teams=teams, total=total)


@app.get("/api/teams/{team_id}", response_model=TeamOut)
def get_team(team_id: int):
    with session_scope() as session:
        t = session.get(Team, team_id)
        if t is None:
            raise HTTPException(404, f"Team {team_id} not found")
        return TeamOut(
            id=t.id,
            name=t.name,
            acronym=t.acronym,
            region=t.region,
            country=t.country,
            image_url=t.image_url,
            current_rating=float(t.current_rating),
            vlr_url=_vlr_team_url(t.vlr_id, t.name),
        )


# ---------------------------------------------------------------------------
# Leaderboard
# ---------------------------------------------------------------------------

@app.get("/api/leaderboard", response_model=LeaderboardResponse)
def leaderboard(
    limit: int = Query(25, ge=1, le=100),
    category: str | None = Query(None, description="Filter by league category"),
    region: str | None = Query(None, description="Filter by region"),
):
    """Top teams by Elo rating with win/loss record.

    Uses a single raw SQL query (two CTEs for wins + losses) for speed.
    """
    with session_scope() as session:
        # Build WHERE filters for the match CTEs
        match_filters = ["m.status = 'finished'", "m.forfeit = false"]
        params: dict[str, Any] = {"lim": limit}

        if category:
            match_filters.append("e.category = :cat")
            params["cat"] = category

        match_where = " AND ".join(match_filters)

        team_filters = ["1=1"]
        if region:
            team_filters.append("t.region = :region")
            params["region"] = region
        team_where = " AND ".join(team_filters)

        event_join = "LEFT JOIN events e ON m.event_id = e.id" if category else ""

        sql = text(f"""
            WITH stats AS (
                SELECT team_id,
                       SUM(wins) AS wins,
                       SUM(losses) AS losses
                FROM (
                    SELECT m.team_a_id AS team_id,
                           SUM(CASE WHEN m.winner_id = m.team_a_id THEN 1 ELSE 0 END) AS wins,
                           SUM(CASE WHEN m.winner_id = m.team_b_id THEN 1 ELSE 0 END) AS losses
                    FROM matches m {event_join}
                    WHERE {match_where}
                    GROUP BY m.team_a_id
                    UNION ALL
                    SELECT m.team_b_id AS team_id,
                           SUM(CASE WHEN m.winner_id = m.team_b_id THEN 1 ELSE 0 END) AS wins,
                           SUM(CASE WHEN m.winner_id = m.team_a_id THEN 1 ELSE 0 END) AS losses
                    FROM matches m {event_join}
                    WHERE {match_where}
                    GROUP BY m.team_b_id
                ) sub
                GROUP BY team_id
            )
            SELECT t.id, t.name, t.acronym, t.region, t.image_url,
                   t.current_rating, t.vlr_id,
                   COALESCE(s.wins, 0) AS wins,
                   COALESCE(s.losses, 0) AS losses
            FROM teams t
            LEFT JOIN stats s ON s.team_id = t.id
            WHERE {team_where}
            ORDER BY t.current_rating DESC
            LIMIT :lim
        """)

        rows = session.execute(sql, params).fetchall()

        entries = []
        for rank, r in enumerate(rows, 1):
            total_matches = r.wins + r.losses
            entries.append(LeaderboardEntry(
                rank=rank,
                team_id=r.id,
                team_name=r.name,
                acronym=r.acronym,
                region=r.region,
                image_url=r.image_url,
                elo_rating=float(r.current_rating),
                win_count=r.wins,
                loss_count=r.losses,
                win_rate=round(r.wins / total_matches, 4) if total_matches else 0.0,
                vlr_url=_vlr_team_url(r.vlr_id, r.name),
            ))

    return LeaderboardResponse(entries=entries, total=len(entries))


# ---------------------------------------------------------------------------
# Upcoming matches with predictions
# ---------------------------------------------------------------------------

@app.get("/api/upcoming", response_model=MatchListResponse)
def upcoming_with_predictions(
    category: str | None = Query(None, description="Filter by league category"),
    region: str | None = Query(None, description="Filter by event region"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """Get upcoming/scheduled matches with predictions attached."""
    with session_scope() as session:
        q = (
            _match_query()
            .where(Match.status.in_(["scheduled", "running"]))
            .order_by(Match.match_date.asc().nullslast())
        )
        count_q = (
            select(func.count())
            .select_from(Match)
            .where(Match.status.in_(["scheduled", "running"]))
        )

        q, count_q = _apply_event_filters(q, count_q, category, region)

        total = session.execute(count_q).scalar() or 0
        rows = session.execute(
            q.offset((page - 1) * page_size).limit(page_size)
        ).all()

        matches = []
        for row in rows:
            m = row[0]
            prediction = None
            if _model and m.team_a_id and m.team_b_id:
                try:
                    features = compute_live_features(
                        m.team_a_id, m.team_b_id, m.best_of or 3
                    )
                    pred = _model.predict(features)
                    prediction = PredictionResponse(
                        team_a_id=m.team_a_id,
                        team_b_id=m.team_b_id,
                        team_a_name=row.ta_name or "",
                        team_b_name=row.tb_name or "",
                        team_a_win_prob=pred.team_a_win_prob,
                        team_b_win_prob=pred.team_b_win_prob,
                        predicted_winner=(
                            (row.ta_name or "") if pred.predicted_winner == "team_a"
                            else (row.tb_name or "")
                        ),
                        confidence=pred.confidence,
                    )
                except Exception as exc:
                    logger.debug("Prediction failed for match %d: %s", m.id, exc)

            matches.append(_row_to_match(row, prediction))

    return MatchListResponse(
        matches=matches, total=total, page=page, page_size=page_size
    )
