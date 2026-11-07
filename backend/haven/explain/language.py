"""Wording rules shared by screeners, rules and the explainer.

Haven reports *possible* signals and things to check, never diagnoses or guarantees. Any
user-facing text Haven generates must avoid the phrases below; tests run every screener note
(and later the explainer's output) through :func:`certainty_phrases`.
"""

import re

BANNED_CERTAINTY_PHRASES: tuple[str, ...] = (
    "has damp",
    "has mould",
    "has mold",
    "is damp",
    "is mouldy",
    "is moldy",
    "damp detected",
    "mould detected",
    "mold detected",
    "definitely",
    "certainly",
    "guaranteed",
    "is confirmed",
    "confirmed damp",
    "confirmed mould",
    "is accessible",
    "is wheelchair accessible",
    "is step-free",
    "is safe",
    "is unsafe",
    "no damp",
    "no mould",
    "free of damp",
    "free of mould",
    "diagnos",
)

_PATTERNS = [
    (phrase, re.compile(r"(?<![a-z])" + re.escape(phrase), re.IGNORECASE))
    for phrase in BANNED_CERTAINTY_PHRASES
]


def certainty_phrases(text: str) -> list[str]:
    """The banned phrases that occur in ``text`` (case-insensitive), in list order."""
    return [phrase for phrase, pattern in _PATTERNS if pattern.search(text)]
