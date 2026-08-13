"""Elo rating system for Valorant teams.

Maintains per-team Elo ratings updated chronologically. Supports K-factor
scaling by event tier (higher-tier events produce larger updates) and optional
map-level Elo.

Usage:
    engine = EloEngine(k=32)
    engine.process_match(team_a_id, team_b_id, winner_id, tier="s")
    rating_a = engine.rating(team_a_id)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

_DEFAULT_RATING = 1500.0

_TIER_K_MULTIPLIER: dict[str, float] = {
    "s": 1.3,       # VCT International
    "a": 1.15,      # VCT Challengers / Ascension
    "b": 1.0,       # Tier-2 regionals
    "c": 0.85,      # Open qualifiers
    "d": 0.7,       # Small community events
    "unranked": 0.8,
}


@dataclass
class EloEngine:
    """Stateful Elo tracker across a chronological match sequence."""

    k: float = 32.0
    initial_rating: float = _DEFAULT_RATING
    _ratings: dict[int, float] = field(default_factory=dict)
    # Per-map Elo: {(team_id, map_name): rating}
    _map_ratings: dict[tuple[int, str], float] = field(default_factory=dict)

    def rating(self, team_id: int) -> float:
        return self._ratings.get(team_id, self.initial_rating)

    def map_rating(self, team_id: int, map_name: str) -> float:
        return self._map_ratings.get((team_id, map_name), self.initial_rating)

    def _expected(self, ra: float, rb: float) -> float:
        return 1.0 / (1.0 + 10 ** ((rb - ra) / 400))

    def process_match(
        self,
        team_a_id: int,
        team_b_id: int,
        winner_id: int | None,
        tier: str | None = None,
    ) -> dict[str, Any]:
        """Update ratings for a single match. Returns pre-update snapshot."""
        ra = self.rating(team_a_id)
        rb = self.rating(team_b_id)
        ea = self._expected(ra, rb)
        eb = 1 - ea

        snapshot = {
            "elo_a": ra,
            "elo_b": rb,
            "elo_expected_a": ea,
            "elo_expected_b": eb,
            "elo_diff": ra - rb,
        }

        if winner_id is None:
            return snapshot

        k = self.k * _TIER_K_MULTIPLIER.get(tier or "unranked", 1.0)
        sa = 1.0 if winner_id == team_a_id else 0.0
        sb = 1.0 - sa

        self._ratings[team_a_id] = ra + k * (sa - ea)
        self._ratings[team_b_id] = rb + k * (sb - eb)
        return snapshot

    def process_map(
        self,
        team_a_id: int,
        team_b_id: int,
        winner_id: int | None,
        map_name: str,
    ) -> dict[str, float]:
        """Update per-map Elo. Returns pre-update ratings."""
        key_a = (team_a_id, map_name)
        key_b = (team_b_id, map_name)
        ra = self._map_ratings.get(key_a, self.initial_rating)
        rb = self._map_ratings.get(key_b, self.initial_rating)
        snapshot = {
            f"map_elo_a_{map_name}": ra,
            f"map_elo_b_{map_name}": rb,
        }

        if winner_id is None:
            return snapshot

        k_map = self.k * 0.75  # Smaller updates for map-level
        ea = self._expected(ra, rb)
        sa = 1.0 if winner_id == team_a_id else 0.0
        self._map_ratings[key_a] = ra + k_map * (sa - ea)
        self._map_ratings[key_b] = rb + k_map * ((1 - sa) - (1 - ea))
        return snapshot

    def snapshot(self) -> dict[int, float]:
        """Return a copy of all current ratings."""
        return dict(self._ratings)
