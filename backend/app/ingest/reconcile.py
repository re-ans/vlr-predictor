"""Reconcile vlr.gg matches to PandaScore matches already in the DB.

The two providers share no IDs and spell teams differently, so we match on the
*set* of normalised team names plus a date window. PandaScore remains the
source of truth: we never create a match from vlr data, we only attach
enrichment to an existing match. Unmatched vlr matches are returned so the
caller can log them for review instead of silently dropping them.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from ..db.models import Match, Team
from .names import normalize_name


class MatchIndex:
    """In-memory index: {frozenset(normalized team names) -> [(match_id, date)]}."""

    def __init__(self, window_days: int = 3) -> None:
        self._index: dict[frozenset[str], list[tuple[int, date | None]]] = {}
        self.window = timedelta(days=window_days)

    @classmethod
    def build(cls, session: Session, window_days: int = 3) -> "MatchIndex":
        idx = cls(window_days=window_days)
        ta = aliased(Team)
        tb = aliased(Team)
        rows = session.execute(
            select(Match.id, Match.match_date, ta.normalized_name, tb.normalized_name)
            .join(ta, Match.team_a_id == ta.id)
            .join(tb, Match.team_b_id == tb.id)
        ).all()
        for match_id, match_date, na, nb in rows:
            if not na or not nb or na == nb:
                continue
            key = frozenset({na, nb})
            d = match_date.date() if isinstance(match_date, datetime) else match_date
            idx._index.setdefault(key, []).append((match_id, d))
        return idx

    def find(self, name1: str, name2: str, when: date | None) -> int | None:
        n1, n2 = normalize_name(name1), normalize_name(name2)
        if not n1 or not n2 or n1 == n2:
            return None
        candidates = self._index.get(frozenset({n1, n2}))
        if not candidates:
            return None
        if len(candidates) == 1 or when is None:
            return candidates[0][0]
        # Multiple meetings of the same two teams -> pick the closest date.
        best_id, best_delta = None, None
        for match_id, mdate in candidates:
            if mdate is None:
                continue
            delta = abs(mdate - when)
            if delta <= self.window and (best_delta is None or delta < best_delta):
                best_id, best_delta = match_id, delta
        return best_id


def parse_listing_date(value: str | None) -> date | None:
    """Parse an event-matches listing date like 'Fri, August 7, 2026'."""
    if not value:
        return None
    for fmt in ("%a, %B %d, %Y", "%A, %B %d, %Y"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    return None
