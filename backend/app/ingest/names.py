"""Team-name normalisation for cross-source reconciliation.

PandaScore and vlr.gg spell team names differently ("FNATIC" vs "Fnatic",
"Leviatán" vs "Leviatan"). We normalise conservatively: casefold, strip
accents, drop punctuation, collapse whitespace. We deliberately do NOT strip
suffixes like "GC" or "Academy" because those distinguish genuinely different
rosters (e.g. "Cloud9" vs "Cloud9 GC").
"""
from __future__ import annotations

import re
import unicodedata

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def normalize_name(name: str | None) -> str:
    if not name:
        return ""
    # Decompose accents and drop combining marks.
    decomposed = unicodedata.normalize("NFKD", name)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    lowered = stripped.casefold()
    collapsed = _NON_ALNUM.sub(" ", lowered).strip()
    return re.sub(r"\s+", " ", collapsed)
