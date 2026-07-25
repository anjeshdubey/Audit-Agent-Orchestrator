"""Deterministic quote-verification — the primary guardrail.

An answer is only trustworthy if its cited passage literally exists in the
source. This check is code, not a model opinion: a paraphrased or invented
quote fails here and can never produce a `documented` verdict.
"""

from __future__ import annotations

import re

from .models import Citation


def normalize(text: str) -> str:
    """Collapse whitespace and lowercase.

    We tolerate whitespace and capitalization differences (models often re-case
    a sentence's first letter) but nothing else — a paraphrase still fails,
    which is exactly what we want to catch.
    """
    return re.sub(r"\s+", " ", text).strip().lower()


# A citation quote must be a real span, not a trivial one. An empty or
# near-empty string is a substring of every document, so it would "verify"
# vacuously — reject anything too short to be a meaningful clause.
MIN_QUOTE_CHARS = 12


def verify_quote(citation: Citation, docs: dict[str, str]) -> bool:
    """True iff the exact_quote is a real, non-trivial span of the cited source."""
    source_text = docs.get(citation.source)
    if source_text is None:
        return False
    needle = normalize(citation.exact_quote)
    if len(needle) < MIN_QUOTE_CHARS:
        return False
    return needle in normalize(source_text)
