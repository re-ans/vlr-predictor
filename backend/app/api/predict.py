"""On-the-fly prediction: compute features for a team pair and run the model.

Maintains a cached snapshot of team stats (Elo, form, last-played, score diffs)
built once from the DB and reused across requests. The cache is refreshed
periodically or on demand.
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, text as sa_text

from ..db.base import build_engine
from ..features.elo import EloEngine

logger = logging.getLogger("api.predict")

_FORM_WINDOWS = [3, 5, 10, 20]
_TIER_ORD = {"s": 5, "a": 4, "b": 3, "c": 2, "d": 1, "unranked": 0}
_CACHE_TTL = 300  # 5 minutes


class _TeamStats:
    __slots__ = ("results", "last_played", "score_diffs")

    def __init__(self) -> None:
        self.results: list[int] = []
        self.last_played: datetime | None = None
        self.score_diffs: list[float] = []

    def form(self, n: int) -> float:
        recent = self.results[-n:]
        return sum(recent) / len(recent) if recent else 0.0

    def avg_score_diff(self) -> float:
        tail = self.score_diffs[-20:]
        return sum(tail) / len(tail) if tail else 0.0


class StatsCache:
    """Precomputed per-team stats for fast prediction serving."""

    def __init__(self) -> None:
        self.elo = EloEngine(k=32)
        self.teams: dict[int, _TeamStats] = defaultdict(_TeamStats)
        self.h2h: dict[frozenset[int], dict[int, int]] = defaultdict(
            lambda: defaultdict(int)
        )
        self._built_at: float = 0

    @property
    def stale(self) -> bool:
        return (time.monotonic() - self._built_at) > _CACHE_TTL

    def build(self) -> None:
        """Replay all finished matches to build the snapshot."""
        t0 = time.monotonic()
        engine = build_engine()
        with engine.connect() as conn:
            rows = conn.execute(sa_text("""
                SELECT m.team_a_id, m.team_b_id, m.winner_id,
                       m.match_date, m.score_a, m.score_b, e.tier
                FROM matches m
                LEFT JOIN events e ON m.event_id = e.id
                WHERE m.status = 'finished'
                  AND m.forfeit = false
                  AND m.winner_id IS NOT NULL
                  AND m.team_a_id IS NOT NULL
                  AND m.team_b_id IS NOT NULL
                ORDER BY m.match_date ASC, m.id ASC
            """)).fetchall()

        self.elo = EloEngine(k=32)
        self.teams = defaultdict(_TeamStats)
        self.h2h = defaultdict(lambda: defaultdict(int))

        for m_a, m_b, w_id, m_date, s_a, s_b, tier in rows:
            self.elo.process_match(m_a, m_b, w_id, tier=tier)

            for tid, is_a in ((m_a, True), (m_b, False)):
                ts = self.teams[tid]
                won = w_id == tid
                ts.results.append(1 if won else 0)
                ts.last_played = m_date
                if s_a is not None and s_b is not None:
                    diff = float(s_a - s_b) if is_a else float(s_b - s_a)
                    ts.score_diffs.append(diff)

            key = frozenset([m_a, m_b])
            self.h2h[key][w_id] += 1

        self._built_at = time.monotonic()
        logger.info("StatsCache built from %d matches in %.1fs",
                     len(rows), time.monotonic() - t0)

    def ensure_fresh(self) -> None:
        if self.stale:
            self.build()


_cache = StatsCache()


def warm_cache() -> None:
    """Call at app startup to pre-build the cache."""
    _cache.build()


def compute_live_features(
    team_a_id: int,
    team_b_id: int,
    best_of: int = 3,
) -> dict[str, Any]:
    """Compute current features for a team pair (fast, from cache).

    Does NOT hit the database — relies entirely on the in-memory snapshot so
    it can be called many times per request without N+1 latency.
    """
    _cache.ensure_fresh()

    elo_a = _cache.elo.rating(team_a_id)
    elo_b = _cache.elo.rating(team_b_id)
    elo_expected_a = _cache.elo._expected(elo_a, elo_b)

    sa = _cache.teams[team_a_id]
    sb = _cache.teams[team_b_id]

    form_feats: dict[str, Any] = {}
    for n in _FORM_WINDOWS:
        form_feats[f"form_a_{n}"] = sa.form(n)
        form_feats[f"form_b_{n}"] = sb.form(n)

    now = datetime.now(timezone.utc)
    days_a = (now - sa.last_played).total_seconds() / 86400 if sa.last_played else 30.0
    days_b = (now - sb.last_played).total_seconds() / 86400 if sb.last_played else 30.0

    h2h_key = frozenset([team_a_id, team_b_id])
    h2h = _cache.h2h.get(h2h_key, {})

    return {
        "elo_a": elo_a,
        "elo_b": elo_b,
        "elo_expected_a": elo_expected_a,
        "elo_expected_b": 1 - elo_expected_a,
        "elo_diff": elo_a - elo_b,
        "best_of": best_of,
        "tier_encoded": 3,
        "h2h_a_wins": h2h.get(team_a_id, 0),
        "h2h_b_wins": h2h.get(team_b_id, 0),
        "h2h_total": sum(h2h.values()),
        "days_since_last_a": days_a,
        "days_since_last_b": days_b,
        "score_diff_avg_a": sa.avg_score_diff(),
        "score_diff_avg_b": sb.avg_score_diff(),
        **form_feats,
    }
