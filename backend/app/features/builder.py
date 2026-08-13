"""Feature builder: generates a training-ready DataFrame from the match database.

Walks matches in chronological order, computing point-in-time features for each
match (using only data available before that match). This prevents look-ahead
bias in training.

Features per match row:
    elo_a, elo_b, elo_diff, elo_expected_a  -- Elo at match time
    form_a_N, form_b_N                      -- Win rate over last N matches
    h2h_a_wins, h2h_b_wins, h2h_total       -- Head-to-head record
    tier_encoded                             -- Event tier ordinal
    best_of                                  -- Match format
    days_since_last_a, days_since_last_b     -- Recency / activity
    score_diff_avg_a, score_diff_avg_b       -- Average map score differential
    winner                                   -- Label: 1 if team_a won, 0 if team_b
"""
from __future__ import annotations

import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
from sqlalchemy import select, text

from ..db.base import build_engine
from .elo import EloEngine

logger = logging.getLogger("features.builder")

_FORM_WINDOWS = [3, 5, 10, 20]
_TIER_ORD: dict[str, int] = {"s": 5, "a": 4, "b": 3, "c": 2, "d": 1, "unranked": 0}

_MATCHES_QUERY = text("""
    SELECT
        m.id,
        m.match_date,
        m.team_a_id,
        m.team_b_id,
        m.winner_id,
        m.best_of,
        m.score_a,
        m.score_b,
        m.forfeit,
        m.status,
        e.tier
    FROM matches m
    LEFT JOIN events e ON m.event_id = e.id
    WHERE m.status = 'finished'
      AND m.forfeit = false
      AND m.winner_id IS NOT NULL
      AND m.team_a_id IS NOT NULL
      AND m.team_b_id IS NOT NULL
    ORDER BY m.match_date ASC, m.id ASC
""")


@dataclass
class _TeamHistory:
    """Rolling history tracker for one team."""
    results: deque[int] = field(default_factory=lambda: deque(maxlen=50))
    last_played: datetime | None = None
    score_diffs: deque[float] = field(default_factory=lambda: deque(maxlen=20))

    def add(self, won: bool, match_date: datetime | None, score_diff: float | None) -> None:
        self.results.append(1 if won else 0)
        if match_date:
            self.last_played = match_date
        if score_diff is not None:
            self.score_diffs.append(score_diff)

    def form(self, n: int) -> float | None:
        recent = list(self.results)[-n:]
        return sum(recent) / len(recent) if recent else None

    def avg_score_diff(self) -> float | None:
        return sum(self.score_diffs) / len(self.score_diffs) if self.score_diffs else None

    def days_since(self, now: datetime | None) -> float | None:
        if self.last_played is None or now is None:
            return None
        delta = now - self.last_played
        return max(delta.total_seconds() / 86400, 0)


@dataclass
class _H2H:
    """Head-to-head record between two teams (keyed by frozenset)."""
    wins: dict[int, int] = field(default_factory=lambda: defaultdict(int))

    def record(self, team_a: int, team_b: int) -> tuple[int, int, int]:
        return self.wins[team_a], self.wins[team_b], sum(self.wins.values())

    def add(self, winner: int) -> None:
        self.wins[winner] += 1


def build_feature_df(min_matches_per_team: int = 3) -> pd.DataFrame:
    """Build the full feature DataFrame from the database.

    Walks matches chronologically, computing point-in-time features.
    Teams with fewer than ``min_matches_per_team`` prior matches are excluded
    from the training set (cold-start rows).
    """
    engine = build_engine()
    with engine.connect() as conn:
        rows = conn.execute(_MATCHES_QUERY).fetchall()

    logger.info("Building features from %d finished non-forfeit matches", len(rows))

    elo = EloEngine(k=32)
    histories: dict[int, _TeamHistory] = defaultdict(_TeamHistory)
    h2h_records: dict[frozenset[int], _H2H] = defaultdict(_H2H)
    records: list[dict[str, Any]] = []

    for row in rows:
        (match_id, match_date, team_a, team_b, winner_id,
         best_of, score_a, score_b, forfeit, status, tier) = row

        ha = histories[team_a]
        hb = histories[team_b]
        key = frozenset([team_a, team_b])
        h2h = h2h_records[key]

        # Count prior matches to filter cold-start
        prior_a = len(ha.results)
        prior_b = len(hb.results)

        # -- Elo features (pre-update) --
        elo_feats = elo.process_match(team_a, team_b, winner_id, tier=tier)

        # -- Form features --
        form_feats: dict[str, Any] = {}
        for n in _FORM_WINDOWS:
            form_feats[f"form_a_{n}"] = ha.form(n)
            form_feats[f"form_b_{n}"] = hb.form(n)

        # -- H2H features --
        h2h_a, h2h_b, h2h_total = h2h.record(team_a, team_b)

        # -- Recency --
        days_a = ha.days_since(match_date)
        days_b = hb.days_since(match_date)

        # -- Score differential --
        sd_a = ha.avg_score_diff()
        sd_b = hb.avg_score_diff()

        # Label
        label = 1 if winner_id == team_a else 0

        rec = {
            "match_id": match_id,
            "match_date": match_date,
            "team_a_id": team_a,
            "team_b_id": team_b,
            "best_of": best_of or 1,
            "tier_encoded": _TIER_ORD.get(tier or "unranked", 0),
            "h2h_a_wins": h2h_a,
            "h2h_b_wins": h2h_b,
            "h2h_total": h2h_total,
            "days_since_last_a": days_a,
            "days_since_last_b": days_b,
            "score_diff_avg_a": sd_a,
            "score_diff_avg_b": sd_b,
            "prior_matches_a": prior_a,
            "prior_matches_b": prior_b,
            "winner": label,
            **elo_feats,
            **form_feats,
        }
        records.append(rec)

        # -- Update trackers AFTER computing features --
        score_diff = None
        if score_a is not None and score_b is not None:
            score_diff = float(score_a - score_b)

        won_a = winner_id == team_a
        ha.add(won_a, match_date, score_diff)
        hb.add(not won_a, match_date, -score_diff if score_diff is not None else None)
        h2h.add(winner_id)

    df = pd.DataFrame(records)
    if df.empty:
        logger.warning("No matches found for feature building")
        return df

    # Filter cold-start rows
    mask = (df["prior_matches_a"] >= min_matches_per_team) & \
           (df["prior_matches_b"] >= min_matches_per_team)
    n_cold = (~mask).sum()
    df = df[mask].reset_index(drop=True)
    logger.info(
        "Feature matrix: %d rows (%d cold-start excluded), %d columns",
        len(df), n_cold, len(df.columns),
    )
    return df
