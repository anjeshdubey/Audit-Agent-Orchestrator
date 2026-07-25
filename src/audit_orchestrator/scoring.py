"""Code-derived verdict and confidence.

The model never reports its own confidence or decides the verdict. Both are
computed here from two explainable signals:

  1. quote-verification  — a hard gate; an unverifiable citation cannot pass.
  2. requirement coverage — the fraction of the control's requirement parts the
     evidence actually addresses.

Keeping this in code (not the prompt) is what makes the confidence score mean
something and keeps the system consistent run to run.
"""

from __future__ import annotations

from .models import Verdict


def derive_verdict_and_confidence(
    *, verified: bool, matched: int, total: int
) -> tuple[Verdict, float]:
    """Return (verdict, confidence) from verification + coverage.

    - documented           : citation verified AND every requirement part covered
    - partially_documented : citation verified AND some (not all) parts covered
    - not_found            : no verified citation, or zero coverage
    """
    coverage = matched / total if total else 0.0

    if verified and coverage >= 1.0:
        return "documented", round(0.85 + 0.10 * coverage, 2)
    if verified and coverage > 0.0:
        return "partially_documented", round(0.45 + 0.35 * coverage, 2)
    return "not_found", 0.60
