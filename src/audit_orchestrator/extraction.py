"""The LLM extraction step — the only part the model owns.

The model is asked, for each requirement part it believes is satisfied, to
supply a separate verbatim citation, plus a rationale. It is NOT asked for the
verdict or a confidence score — those are derived in code from the verified
evidence. Splitting evidence per requirement part means a control whose proof
lives in two places gets two exact quotes, each independently verifiable,
instead of one stitched-together (and unverifiable) paraphrase.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from .gateway import GatewayConfig, extract
from .models import Citation, Control

SYSTEM_PROMPT = (
    "You are an audit evidence assistant performing DESIGN/DOCUMENTATION testing: "
    "you determine whether a control is adequately documented in the provided "
    "policy documents. You never conclude on operating effectiveness. For each "
    "requirement part you believe is satisfied, provide ONE finding whose "
    "citation quotes the supporting text VERBATIM — copy it exactly, no "
    "paraphrasing, no stitching two sentences together, no ellipsis. A passage "
    "supports a part only if it EXPLICITLY states that part's specific claim — "
    "do not reuse the same passage for a part it does not directly address, and "
    "do not treat a general statement as covering a specific requirement (e.g. "
    "'protected using encryption' does not establish key management or rotation; "
    "'reviewed periodically' does not establish a quarterly cadence). If a part "
    "is not supported, do not include a finding for it. If nothing supports the "
    "control, return an empty findings list."
)


class Finding(BaseModel):
    """One satisfied requirement part with its own verbatim citation."""

    requirement_part: str = Field(
        description="The exact requirement-part string (copied from the list) "
        "that this citation supports."
    )
    citation: Citation


class ExtractionResult(BaseModel):
    """What the model returns — evidence only, no verdict or confidence."""

    findings: list[Finding] = Field(
        default_factory=list,
        description="One finding per satisfied requirement part. Empty if none.",
    )
    rationale: str = Field(
        description="One or two sentences explaining the assessment."
    )


def _build_user_prompt(control: Control, docs: dict[str, str]) -> str:
    doc_bundle = "\n\n".join(
        f"=== FILE: {name} ===\n{text}" for name, text in docs.items()
    )
    parts = "\n".join(f"  - {p}" for p in control.requirement_parts)
    return (
        f"CONTROL {control.id} — {control.title}\n"
        f"Requirement: {control.requirement.strip()}\n"
        f"Requirement parts (use these exact strings as requirement_part):\n{parts}\n\n"
        f"Test procedure: {control.test_procedure.strip()}\n\n"
        f"DOCUMENTS:\n{doc_bundle}"
    )


def extract_evidence(
    control: Control, docs: dict[str, str], *, config: GatewayConfig | None = None
) -> tuple[ExtractionResult, GatewayConfig]:
    """Run the model to gather evidence for one control."""
    return extract(
        response_model=ExtractionResult,
        system_prompt=SYSTEM_PROMPT,
        user_prompt=_build_user_prompt(control, docs),
        config=config,
    )
