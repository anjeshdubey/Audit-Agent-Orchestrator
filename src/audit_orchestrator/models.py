"""Core data models shared across the testing agent."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Verdict = Literal["documented", "partially_documented", "not_found"]


class Control(BaseModel):
    """One requirement to be tested against the evidence documents."""

    id: str
    title: str
    requirement: str
    requirement_parts: list[str] = Field(
        description="The distinct sub-claims of the requirement. Coverage of "
        "these parts (each backed by a verified citation) drives the verdict "
        "and confidence."
    )
    test_procedure: str
    expected_evidence: str | None = None


class Citation(BaseModel):
    """A pointer to the exact source passage supporting one requirement part."""

    source: str = Field(description="Filename of the evidence document.")
    anchor: str = Field(description="Section/heading the quote sits under.")
    exact_quote: str = Field(
        description="A verbatim span from the source — must appear as written."
    )


class EvidenceItem(BaseModel):
    """A single requirement part backed by a verified citation."""

    requirement_part: str
    citation: Citation


class ControlAssessment(BaseModel):
    """The tested result for a single control. Verdict and confidence are
    derived in code (see scoring.py), never taken from the model. Only
    verified evidence appears in `evidence`."""

    control_id: str
    title: str
    verdict: Verdict
    confidence: float
    coverage_matched: int
    coverage_total: int
    rationale: str
    evidence: list[EvidenceItem] = Field(default_factory=list)
    rejected_citations: int = Field(
        default=0,
        description="How many proposed citations failed verification (their "
        "quote was not found in the source) — fabrications caught.",
    )


class Workpaper(BaseModel):
    """The full engagement result — the deliverable of the testing agent."""

    engagement: str
    generated_at: str
    provider: str
    model: str
    scope_note: str
    summary: dict[str, int]
    assessments: list[ControlAssessment]
    # Evidence text is embedded so the viewer is a self-contained artifact that
    # can highlight the cited passage inside the real source document.
    evidence_documents: dict[str, str] = Field(default_factory=dict)
