"""SQLAlchemy ORM models = the Postgres source of truth.

Design notes
------------
* Every table has its own surrogate ``id`` PK. Source identifiers from
  PandaScore and vlr.gg are stored in separate nullable ``pandascore_id`` /
  ``vlr_id`` columns because the two providers do NOT share IDs. This is what
  makes cross-source reconciliation (Phase 3) possible.
* ``normalized_name`` on teams supports name-variant matching
  ("FNATIC" vs "Fnatic").
* All vlr.gg-sourced enrichment fields (maps, per-player stats) are nullable so
  a gap in the local scraper path never breaks the PandaScore source of truth.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

# Stable constraint naming so Alembic autogenerate diffs are deterministic.
Base.metadata = MetaData(
    naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }
)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Team(TimestampMixin, Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str | None] = mapped_column(String(255), index=True)
    acronym: Mapped[str | None] = mapped_column(String(32))
    region: Mapped[str | None] = mapped_column(String(32), index=True)
    country: Mapped[str | None] = mapped_column(String(64))
    image_url: Mapped[str | None] = mapped_column(Text)
    # Elo-style rating, maintained incrementally (Phase 4).
    current_rating: Mapped[float] = mapped_column(
        Numeric(8, 2), nullable=False, server_default="1500"
    )

    pandascore_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)
    vlr_id: Mapped[str | None] = mapped_column(String(32), unique=True)

    players: Mapped[list["Player"]] = relationship(back_populates="team")


class Player(TimestampMixin, Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    team_id: Mapped[int | None] = mapped_column(
        ForeignKey("teams.id", ondelete="SET NULL"), index=True
    )
    country: Mapped[str | None] = mapped_column(String(64))

    pandascore_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)
    vlr_id: Mapped[str | None] = mapped_column(String(32), unique=True)

    team: Mapped["Team | None"] = relationship(back_populates="players")


class Event(TimestampMixin, Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    tier: Mapped[str | None] = mapped_column(String(16), index=True)
    # Coarse league bucket for UI filtering (vct-intl|vct|gc|challengers|tier3).
    category: Mapped[str | None] = mapped_column(String(16), index=True)
    region: Mapped[str | None] = mapped_column(String(32), index=True)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    prize_pool: Mapped[float | None] = mapped_column(Numeric(14, 2))

    pandascore_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)
    vlr_id: Mapped[str | None] = mapped_column(String(32), unique=True)

    matches: Mapped[list["Match"]] = relationship(back_populates="event")


class Match(TimestampMixin, Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    event_id: Mapped[int | None] = mapped_column(
        ForeignKey("events.id", ondelete="SET NULL"), index=True
    )
    team_a_id: Mapped[int | None] = mapped_column(
        ForeignKey("teams.id", ondelete="SET NULL"), index=True
    )
    team_b_id: Mapped[int | None] = mapped_column(
        ForeignKey("teams.id", ondelete="SET NULL"), index=True
    )
    winner_id: Mapped[int | None] = mapped_column(
        ForeignKey("teams.id", ondelete="SET NULL")
    )
    match_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    best_of: Mapped[int | None] = mapped_column(Integer)
    # scheduled | running | finished | canceled | postponed
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    score_a: Mapped[int | None] = mapped_column(Integer)
    score_b: Mapped[int | None] = mapped_column(Integer)
    # Walkover/forfeit — exclude from model training (not a real result).
    forfeit: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )

    pandascore_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)
    vlr_id: Mapped[str | None] = mapped_column(String(32), unique=True)
    # True once vlr.gg enrichment (maps/player stats) has been attached.
    enriched: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )

    event: Mapped["Event | None"] = relationship(back_populates="matches")
    maps: Mapped[list["MatchMap"]] = relationship(
        back_populates="match", cascade="all, delete-orphan"
    )


class MatchMap(TimestampMixin, Base):
    __tablename__ = "match_maps"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    match_id: Mapped[int] = mapped_column(
        ForeignKey("matches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    map_name: Mapped[str | None] = mapped_column(String(64))
    map_order: Mapped[int | None] = mapped_column(Integer)
    picked_by: Mapped[str | None] = mapped_column(String(255))
    team_a_score: Mapped[int | None] = mapped_column(Integer)
    team_b_score: Mapped[int | None] = mapped_column(Integer)
    winner_id: Mapped[int | None] = mapped_column(
        ForeignKey("teams.id", ondelete="SET NULL")
    )

    match: Mapped["Match"] = relationship(back_populates="maps")
    player_stats: Mapped[list["MatchPlayerStats"]] = relationship(
        back_populates="match_map", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("match_id", "map_order", name="uq_match_maps_match_order"),
    )


class MatchPlayerStats(TimestampMixin, Base):
    __tablename__ = "match_player_stats"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    match_map_id: Mapped[int] = mapped_column(
        ForeignKey("match_maps.id", ondelete="CASCADE"), nullable=False, index=True
    )
    player_id: Mapped[int | None] = mapped_column(
        ForeignKey("players.id", ondelete="SET NULL"), index=True
    )
    team_id: Mapped[int | None] = mapped_column(
        ForeignKey("teams.id", ondelete="SET NULL")
    )
    agent: Mapped[str | None] = mapped_column(String(64))
    kills: Mapped[int | None] = mapped_column(Integer)
    deaths: Mapped[int | None] = mapped_column(Integer)
    assists: Mapped[int | None] = mapped_column(Integer)
    acs: Mapped[float | None] = mapped_column(Numeric(7, 2))
    rating: Mapped[float | None] = mapped_column(Numeric(6, 3))
    adr: Mapped[float | None] = mapped_column(Numeric(7, 2))

    match_map: Mapped["MatchMap"] = relationship(back_populates="player_stats")


class RankingsSnapshot(TimestampMixin, Base):
    __tablename__ = "rankings_snapshots"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    region: Mapped[str | None] = mapped_column(String(32), index=True)
    rank: Mapped[int | None] = mapped_column(Integer)
    rating: Mapped[float | None] = mapped_column(Numeric(8, 2))
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint(
            "team_id", "snapshot_date", name="uq_rankings_snapshots_team_date"
        ),
    )


class User(TimestampMixin, Base):
    """A registered user (email + password auth)."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(64))

    favorite_teams: Mapped[list["FavoriteTeam"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    saved_matches: Mapped[list["SavedMatch"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    saved_predictions: Mapped[list["SavedPrediction"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    rosters: Mapped[list["CustomRoster"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class FavoriteTeam(TimestampMixin, Base):
    __tablename__ = "favorite_teams"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True
    )

    user: Mapped["User"] = relationship(back_populates="favorite_teams")

    __table_args__ = (
        UniqueConstraint("user_id", "team_id", name="uq_favorite_teams_user_team"),
    )


class SavedMatch(TimestampMixin, Base):
    __tablename__ = "saved_matches"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    match_id: Mapped[int] = mapped_column(
        ForeignKey("matches.id", ondelete="CASCADE"), nullable=False, index=True
    )

    user: Mapped["User"] = relationship(back_populates="saved_matches")

    __table_args__ = (
        UniqueConstraint("user_id", "match_id", name="uq_saved_matches_user_match"),
    )


class SavedPrediction(TimestampMixin, Base):
    """A point-in-time snapshot of the model's prediction for a matchup."""

    __tablename__ = "saved_predictions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Optional link to a real scheduled/finished match (for correctness tracking).
    match_id: Mapped[int | None] = mapped_column(
        ForeignKey("matches.id", ondelete="SET NULL"), index=True
    )
    team_a_id: Mapped[int | None] = mapped_column(
        ForeignKey("teams.id", ondelete="SET NULL")
    )
    team_b_id: Mapped[int | None] = mapped_column(
        ForeignKey("teams.id", ondelete="SET NULL")
    )
    team_a_name: Mapped[str] = mapped_column(String(255), nullable=False)
    team_b_name: Mapped[str] = mapped_column(String(255), nullable=False)
    prob_a: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False)
    prob_b: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False)
    predicted_winner: Mapped[str] = mapped_column(String(255), nullable=False)
    best_of: Mapped[int | None] = mapped_column(Integer)

    user: Mapped["User"] = relationship(back_populates="saved_predictions")


class CustomRoster(TimestampMixin, Base):
    """A user-defined named lineup of players (groundwork for a future
    roster-aware prediction model — does not drive predictions yet)."""

    __tablename__ = "custom_rosters"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)

    user: Mapped["User"] = relationship(back_populates="rosters")
    players: Mapped[list["CustomRosterPlayer"]] = relationship(
        back_populates="roster", cascade="all, delete-orphan"
    )


class CustomRosterPlayer(TimestampMixin, Base):
    __tablename__ = "custom_roster_players"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    roster_id: Mapped[int] = mapped_column(
        ForeignKey("custom_rosters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    player_id: Mapped[int] = mapped_column(
        ForeignKey("players.id", ondelete="CASCADE"), nullable=False, index=True
    )

    roster: Mapped["CustomRoster"] = relationship(back_populates="players")

    __table_args__ = (
        UniqueConstraint(
            "roster_id", "player_id", name="uq_custom_roster_players_roster_player"
        ),
    )


class IngestionRun(TimestampMixin, Base):
    """Audit log for every ingestion run (both PandaScore and vlrggapi paths)."""

    __tablename__ = "ingestion_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    job: Mapped[str] = mapped_column(String(64), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[float | None] = mapped_column(Numeric(10, 3))
    rows_written: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    errors: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    # running | success | failed | partial
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    message: Mapped[str | None] = mapped_column(Text)
