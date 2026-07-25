"""Phase 0.5 spike — prove the core promise before building anything else.

For each control in the sample program, ask an LLM to find supporting evidence
in the sample policy documents and return a *citation* (source + section +
exact quote). Then the part that matters: deterministically verify the quoted
passage literally exists in the named document. The model does not get to
decide the verdict or its own confidence — code derives both from two
explainable signals:

    1. quote-verification  (hard gate: an unverifiable quote is rejected)
    2. requirement coverage (how many of the control's requirement parts the
       evidence actually addresses)

This is a throwaway script. No persistence, no UI, no retrieval — the whole
point is to confirm a grounded, verifiable answer is reliable enough to build
the MVP on.

Run:
    python spike/phase_0_5.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from audit_orchestrator.gateway import GatewayError, extract  # noqa: E402

SAMPLE_DIR = Path(__file__).resolve().parent / "sample"
EVIDENCE_FILES = ["onboarding-policy.md", "access-control-policy.md"]


# --- What we ask the model for (note: NOT the verdict, NOT the confidence) ---


class Citation(BaseModel):
    source: str = Field(
        description="Exact filename of the document, e.g. 'onboarding-policy.md'."
    )
    anchor: str = Field(description="Section/heading the quote is under, e.g. '§4.2'.")
    exact_quote: str = Field(
        description="A verbatim span copied from the document — no paraphrasing, "
        "no ellipsis. Must appear exactly as written in the source."
    )


class ExtractionResult(BaseModel):
    matched_parts: list[str] = Field(
        default_factory=list,
        description="Which of the control's requirement_parts the evidence "
        "satisfies. Copy the strings verbatim from the provided list. Empty if none.",
    )
    citation: Citation | None = Field(
        default=None,
        description="The single best supporting passage, or null if the "
        "document set does not support this control.",
    )
    rationale: str = Field(
        description="One or two sentences explaining the assessment."
    )


SYSTEM_PROMPT = (
    "You are an audit evidence assistant performing DESIGN/DOCUMENTATION testing: "
    "you determine whether a control is adequately documented in the provided "
    "policy documents. You never conclude on operating effectiveness. When you "
    "cite evidence you must copy the supporting text VERBATIM — an inexact quote "
    "is worse than no quote. If nothing in the documents supports the control, "
    "return no citation and an empty matched_parts list."
)


def normalize(text: str) -> str:
    """Collapse whitespace and lowercase for a lenient-but-honest quote check.

    We tolerate whitespace and capitalization differences (models often
    re-case a sentence's first letter) but nothing else — a paraphrase still
    fails, which is the whole point.
    """
    return re.sub(r"\s+", " ", text).strip().lower()


def verify_quote(citation: Citation, docs: dict[str, str]) -> bool:
    """True iff the exact_quote actually appears in the cited source document."""
    source_text = docs.get(citation.source)
    if source_text is None:
        return False
    return normalize(citation.exact_quote) in normalize(source_text)


def derive_verdict_and_confidence(
    *, verified: bool, matched: int, total: int
) -> tuple[str, float]:
    """Code owns the verdict and confidence — never the model.

    Confidence is built from two explainable factors, not a model's opinion:
    a verified citation is the gate, and requirement coverage scales it.
    """
    coverage = matched / total if total else 0.0

    if verified and coverage >= 1.0:
        return "documented", round(0.85 + 0.10 * coverage, 2)
    if verified and coverage > 0.0:
        return "partially_documented", round(0.45 + 0.35 * coverage, 2)
    return "not_found", 0.60


def assess_control(control: dict, docs: dict[str, str]) -> dict:
    parts = control.get("requirement_parts", [])
    doc_bundle = "\n\n".join(
        f"=== FILE: {name} ===\n{text}" for name, text in docs.items()
    )
    user_prompt = (
        f"CONTROL {control['id']} — {control['title']}\n"
        f"Requirement: {control['requirement'].strip()}\n"
        f"Requirement parts (use these exact strings in matched_parts):\n"
        + "\n".join(f"  - {p}" for p in parts)
        + f"\n\nTest procedure: {control['test_procedure'].strip()}\n\n"
        f"DOCUMENTS:\n{doc_bundle}"
    )

    result, config = extract(
        response_model=ExtractionResult,
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
    )

    # Guard against a model inflating coverage by inventing parts: only count
    # matched_parts that are actually declared on the control.
    valid_matched = [p for p in result.matched_parts if p in parts]
    verified = result.citation is not None and verify_quote(result.citation, docs)
    citation_rejected = result.citation is not None and not verified

    # A verified citation with zero real coverage is contradictory — drop it.
    effective_verified = verified and len(valid_matched) > 0

    verdict, confidence = derive_verdict_and_confidence(
        verified=effective_verified,
        matched=len(valid_matched),
        total=len(parts),
    )

    return {
        "control_id": control["id"],
        "title": control["title"],
        "verdict": verdict,
        "confidence": confidence,
        "coverage": f"{len(valid_matched)}/{len(parts)}",
        "citation": result.citation.model_dump() if verified else None,
        "citation_rejected": citation_rejected,
        "rationale": result.rationale,
        "provider": config.provider,
        "model": config.model,
    }


def print_report(rows: list[dict]) -> None:
    symbols = {"documented": "✓", "partially_documented": "~", "not_found": "✗"}
    print("\n" + "=" * 72)
    print("PHASE 0.5 — grounded extraction with deterministic quote-verification")
    print("=" * 72)
    for r in rows:
        print(f"\n{symbols[r['verdict']]} {r['control_id']} — {r['title']}")
        print(f"    verdict     : {r['verdict']}  (confidence {r['confidence']})")
        print(f"    coverage    : {r['coverage']} requirement parts")
        print(f"    rationale   : {r['rationale']}")
        if r["citation"]:
            c = r["citation"]
            print(f"    citation    : {c['source']} {c['anchor']}")
            print(f"                  \"{c['exact_quote']}\"  [VERIFIED in source]")
        elif r["citation_rejected"]:
            print(
                "    citation    : REJECTED — model's quote was not found in the "
                "source (fabrication caught)"
            )
        else:
            print("    citation    : none")
    print(f"\n{'-' * 72}")
    print(f"Ran on provider={rows[0]['provider']} model={rows[0]['model']}")
    print("-" * 72 + "\n")


def main() -> int:
    load_dotenv()
    docs = {name: (SAMPLE_DIR / name).read_text() for name in EVIDENCE_FILES}
    controls = yaml.safe_load((SAMPLE_DIR / "controls.yaml").read_text())

    try:
        rows = [assess_control(c, docs) for c in controls]
    except GatewayError as e:
        print(f"\nGateway not configured: {e}\n", file=sys.stderr)
        print("Copy .env.example to .env and set one provider key.", file=sys.stderr)
        return 1

    print_report(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
