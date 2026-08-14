"""User profile API: auth, favorites, saved matches/predictions, rosters."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..db.base import session_scope
from ..db.models import (
    CustomRoster,
    CustomRosterPlayer,
    FavoriteTeam,
    Match,
    Player,
    SavedMatch,
    SavedPrediction,
    Team,
    User,
)
from .auth import (
    create_token,
    get_current_user,
    hash_password,
    verify_password,
)
from .schemas import (
    AuthResponse,
    CreateRosterRequest,
    LoginRequest,
    PlayerOut,
    RegisterRequest,
    RosterOut,
    SavedPredictionOut,
    SavePredictionRequest,
    UserOut,
)

router = APIRouter(prefix="/api", tags=["profile"])


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@router.post("/auth/register", response_model=AuthResponse, status_code=201)
def register(body: RegisterRequest):
    if len(body.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")
    with session_scope() as session:
        existing = session.execute(
            select(User.id).where(User.email == body.email.lower().strip())
        ).scalar_one_or_none()
        if existing:
            raise HTTPException(409, "Email already registered")
        user = User(
            email=body.email.lower().strip(),
            password_hash=hash_password(body.password),
            display_name=body.display_name,
        )
        session.add(user)
        session.flush()
        token = create_token(user.id, user.email)
        return AuthResponse(
            token=token,
            user=UserOut(id=user.id, email=user.email, display_name=user.display_name),
        )


@router.post("/auth/login", response_model=AuthResponse)
def login(body: LoginRequest):
    with session_scope() as session:
        user = session.execute(
            select(User).where(User.email == body.email.lower().strip())
        ).scalar_one_or_none()
        if user is None or not verify_password(body.password, user.password_hash):
            raise HTTPException(401, "Invalid email or password")
        token = create_token(user.id, user.email)
        return AuthResponse(
            token=token,
            user=UserOut(id=user.id, email=user.email, display_name=user.display_name),
        )


@router.get("/auth/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return UserOut(id=user.id, email=user.email, display_name=user.display_name)


# ---------------------------------------------------------------------------
# Favorite teams
# ---------------------------------------------------------------------------

@router.post("/profile/favorites/{team_id}", status_code=201)
def add_favorite(team_id: int, user: User = Depends(get_current_user)):
    with session_scope() as session:
        team = session.get(Team, team_id)
        if not team:
            raise HTTPException(404, "Team not found")
        try:
            fav = FavoriteTeam(user_id=user.id, team_id=team_id)
            session.add(fav)
            session.flush()
        except IntegrityError:
            raise HTTPException(409, "Already favorited")
    return {"ok": True}


@router.delete("/profile/favorites/{team_id}")
def remove_favorite(team_id: int, user: User = Depends(get_current_user)):
    with session_scope() as session:
        fav = session.execute(
            select(FavoriteTeam).where(
                FavoriteTeam.user_id == user.id, FavoriteTeam.team_id == team_id
            )
        ).scalar_one_or_none()
        if fav:
            session.delete(fav)
    return {"ok": True}


@router.get("/profile/favorites")
def list_favorites(user: User = Depends(get_current_user)):
    with session_scope() as session:
        rows = session.execute(
            select(FavoriteTeam.team_id, Team.name, Team.image_url, Team.current_rating)
            .join(Team, FavoriteTeam.team_id == Team.id)
            .where(FavoriteTeam.user_id == user.id)
            .order_by(FavoriteTeam.created_at.desc())
        ).all()
    return {
        "favorites": [
            {"team_id": r[0], "name": r[1], "image_url": r[2], "rating": float(r[3])}
            for r in rows
        ]
    }


# ---------------------------------------------------------------------------
# Saved matches
# ---------------------------------------------------------------------------

@router.post("/profile/matches/{match_id}", status_code=201)
def save_match(match_id: int, user: User = Depends(get_current_user)):
    with session_scope() as session:
        if not session.get(Match, match_id):
            raise HTTPException(404, "Match not found")
        try:
            sm = SavedMatch(user_id=user.id, match_id=match_id)
            session.add(sm)
            session.flush()
        except IntegrityError:
            raise HTTPException(409, "Match already saved")
    return {"ok": True}


@router.delete("/profile/matches/{match_id}")
def unsave_match(match_id: int, user: User = Depends(get_current_user)):
    with session_scope() as session:
        sm = session.execute(
            select(SavedMatch).where(
                SavedMatch.user_id == user.id, SavedMatch.match_id == match_id
            )
        ).scalar_one_or_none()
        if sm:
            session.delete(sm)
    return {"ok": True}


@router.get("/profile/matches")
def list_saved_matches(user: User = Depends(get_current_user)):
    with session_scope() as session:
        rows = session.execute(
            select(SavedMatch.match_id).where(SavedMatch.user_id == user.id)
            .order_by(SavedMatch.created_at.desc())
        ).scalars().all()
    return {"match_ids": list(rows)}


# ---------------------------------------------------------------------------
# Saved predictions
# ---------------------------------------------------------------------------

@router.post("/profile/predictions", response_model=SavedPredictionOut, status_code=201)
def save_prediction(
    body: SavePredictionRequest, user: User = Depends(get_current_user)
):
    with session_scope() as session:
        sp = SavedPrediction(
            user_id=user.id,
            match_id=body.match_id,
            team_a_id=body.team_a_id,
            team_b_id=body.team_b_id,
            team_a_name=body.team_a_name,
            team_b_name=body.team_b_name,
            prob_a=body.prob_a,
            prob_b=body.prob_b,
            predicted_winner=body.predicted_winner,
            best_of=body.best_of,
        )
        session.add(sp)
        session.flush()
        return SavedPredictionOut(
            id=sp.id,
            match_id=sp.match_id,
            team_a_id=sp.team_a_id,
            team_b_id=sp.team_b_id,
            team_a_name=sp.team_a_name,
            team_b_name=sp.team_b_name,
            prob_a=float(sp.prob_a),
            prob_b=float(sp.prob_b),
            predicted_winner=sp.predicted_winner,
            best_of=sp.best_of,
            created_at=sp.created_at,
        )


@router.get("/profile/predictions")
def list_saved_predictions(user: User = Depends(get_current_user)):
    with session_scope() as session:
        rows = session.execute(
            select(SavedPrediction)
            .where(SavedPrediction.user_id == user.id)
            .order_by(SavedPrediction.created_at.desc())
        ).scalars().all()
        return {
            "predictions": [
                SavedPredictionOut(
                    id=sp.id,
                    match_id=sp.match_id,
                    team_a_id=sp.team_a_id,
                    team_b_id=sp.team_b_id,
                    team_a_name=sp.team_a_name,
                    team_b_name=sp.team_b_name,
                    prob_a=float(sp.prob_a),
                    prob_b=float(sp.prob_b),
                    predicted_winner=sp.predicted_winner,
                    best_of=sp.best_of,
                    created_at=sp.created_at,
                )
                for sp in rows
            ]
        }


@router.delete("/profile/predictions/{prediction_id}")
def delete_prediction(prediction_id: int, user: User = Depends(get_current_user)):
    with session_scope() as session:
        sp = session.execute(
            select(SavedPrediction).where(
                SavedPrediction.id == prediction_id,
                SavedPrediction.user_id == user.id,
            )
        ).scalar_one_or_none()
        if not sp:
            raise HTTPException(404, "Prediction not found")
        session.delete(sp)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Custom rosters
# ---------------------------------------------------------------------------

@router.post("/profile/rosters", response_model=RosterOut, status_code=201)
def create_roster(
    body: CreateRosterRequest, user: User = Depends(get_current_user)
):
    with session_scope() as session:
        roster = CustomRoster(user_id=user.id, name=body.name)
        session.add(roster)
        session.flush()
        for pid in body.player_ids:
            if session.get(Player, pid):
                session.add(CustomRosterPlayer(roster_id=roster.id, player_id=pid))
        session.flush()
        return RosterOut(
            id=roster.id,
            name=roster.name,
            player_ids=body.player_ids,
            created_at=roster.created_at,
        )


@router.get("/profile/rosters")
def list_rosters(user: User = Depends(get_current_user)):
    with session_scope() as session:
        rosters = session.execute(
            select(CustomRoster)
            .where(CustomRoster.user_id == user.id)
            .order_by(CustomRoster.created_at.desc())
        ).scalars().all()
        result = []
        for r in rosters:
            pids = session.execute(
                select(CustomRosterPlayer.player_id)
                .where(CustomRosterPlayer.roster_id == r.id)
            ).scalars().all()
            result.append(RosterOut(
                id=r.id, name=r.name, player_ids=list(pids), created_at=r.created_at
            ))
        return {"rosters": result}


@router.delete("/profile/rosters/{roster_id}")
def delete_roster(roster_id: int, user: User = Depends(get_current_user)):
    with session_scope() as session:
        roster = session.execute(
            select(CustomRoster).where(
                CustomRoster.id == roster_id, CustomRoster.user_id == user.id
            )
        ).scalar_one_or_none()
        if not roster:
            raise HTTPException(404, "Roster not found")
        session.delete(roster)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Player search (for roster builder)
# ---------------------------------------------------------------------------

@router.get("/players", response_model=list[PlayerOut])
def search_players(q: str = Query("", min_length=0), limit: int = 20):
    with session_scope() as session:
        stmt = select(Player, Team.name.label("team_name")).outerjoin(
            Team, Player.team_id == Team.id
        )
        if q:
            stmt = stmt.where(Player.name.ilike(f"%{q}%"))
        stmt = stmt.order_by(Player.name).limit(limit)
        rows = session.execute(stmt).all()
        return [
            PlayerOut(
                id=p.id,
                name=p.name,
                team_id=p.team_id,
                team_name=tn,
                country=p.country,
            )
            for p, tn in rows
        ]
