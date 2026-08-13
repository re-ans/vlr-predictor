"""League/tier classification for events.

Maps a PandaScore event (name + tier + region) to a coarse ``category`` used
for filtering in the UI. Categories:

* ``vct-intl``   - VCT International: Masters & Champions
* ``vct``        - VCT franchised leagues: Americas / EMEA / Pacific / China
* ``gc``         - Game Changers (all regions)
* ``challengers``- Challengers / regional Tier-2 leagues
* ``tier3``      - Community / Tier-3 / everything else

The classifier is name-first (most reliable), falling back to the PandaScore
tier code.
"""
from __future__ import annotations

CATEGORY_LABELS: dict[str, str] = {
    "vct-intl": "VCT International",
    "vct": "VCT Leagues",
    "gc": "Game Changers",
    "challengers": "Challengers (T2)",
    "tier3": "Tier 3",
}

_VCT_INTL_KEYWORDS = ("masters", "champions")
_VCT_LEAGUE_KEYWORDS = (
    "americas", "emea", "pacific", "vct china", "china stage", "china  stage",
)
_CHALLENGERS_KEYWORDS = ("challengers", "ascension")


def classify_league(name: str | None, tier: str | None, region: str | None = None) -> str:
    """Return a coarse league category for an event."""
    n = (name or "").lower().strip()

    # Game Changers takes priority regardless of tier.
    if "game changers" in n or n.startswith("gc ") or " gc " in n:
        return "gc"

    if any(k in n for k in _VCT_INTL_KEYWORDS):
        return "vct-intl"

    if any(k in n for k in _VCT_LEAGUE_KEYWORDS):
        return "vct"

    if any(k in n for k in _CHALLENGERS_KEYWORDS):
        return "challengers"

    # Fall back to tier code.
    t = (tier or "").lower()
    if t == "s":
        return "vct-intl"
    if t == "a":
        return "vct"
    if t in ("b", "c"):
        return "challengers"
    return "tier3"
