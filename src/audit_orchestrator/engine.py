"""The testing agent: assess each control, assemble the workpaper.

Per control: extract evidence (model) -> verify the cited quote (code) ->
derive verdict + confidence (code). The model proposes; code disposes.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from .extraction import extract_evidence
from .gateway import GatewayConfig, GatewayError
from .models import Control, ControlAssessment, EvidenceItem, Workpaper
from .scoring import derive_verdict_and_confidence
from .verify import verify_quote

SCOPE_NOTE = (
    "Design/documentation testing only: assesses whether each control is "
    "adequately documented in the provided policies. Does not test operating "
    "effectiveness (sampling, record-level testing). A 'documented' verdict is "
    "not an operating-effectiveness pass."
)


def assess_control(
    control: Control, docs: dict[str, str], *, config: GatewayConfig | None = None
) -> tuple[ControlAssessment, GatewayConfig | None]:
    # GatewayError only occurs when `config` is None and env resolution itself
    # fails (no API key configured at all) — that's a setup problem, so it
    # propagates and the whole run fails fast. Any other exception here is a
    # transient runtime failure of THIS control's request (rate limit, 503,
    # timeout — the exact failure class we hit live against Groq's daily cap).
    # That must not discard every control already assessed in this run, so it
    # is caught and turned into an errored assessment instead of a crash.
    try:
        result, used_config = extract_evidence(control, docs, config=config)
    except GatewayError:
        raise
    except Exception as e:  # noqa: BLE001 - any provider/SDK failure, caught broadly
        errored = ControlAssessment(
            control_id=control.id,
            title=control.title,
            verdict="not_found",
            confidence=0.0,
            coverage_matched=0,
            coverage_total=len(control.requirement_parts),
            rationale=f"Extraction failed and this control was not assessed: {e}",
            evidence=[],
            rejected_citations=0,
            error=str(e),
        )
        return errored, config

    # Keep only findings that (a) name a requirement part actually declared on
    # the control and (b) whose quote verifies against the source. Coverage is
    # therefore parts backed by *verified* evidence — a fabricated or invented
    # quote simply doesn't count.
    #
    # Note the deliberate boundary: verification proves a quote is *authentic*,
    # not that it is *relevant*. The model can still attach a real passage to a
    # part it doesn't truly support (semantic sufficiency), and a single
    # sentence can legitimately satisfy several requirement facets. We do not
    # judge relevance in code — that is exactly what the human reviewer signs
    # off on in the HITL phase. The prompt pushes the model toward precision;
    # the reviewer is the backstop.
    evidence: list[EvidenceItem] = []
    covered_parts: set[str] = set()
    rejected = 0
    for finding in result.findings:
        if finding.requirement_part not in control.requirement_parts:
            continue
        if not verify_quote(finding.citation, docs):
            rejected += 1
            continue
        if finding.requirement_part in covered_parts:
            continue
        covered_parts.add(finding.requirement_part)
        evidence.append(
            EvidenceItem(
                requirement_part=finding.requirement_part, citation=finding.citation
            )
        )

    matched = len(covered_parts)
    total = len(control.requirement_parts)
    verdict, confidence = derive_verdict_and_confidence(
        verified=matched > 0, matched=matched, total=total
    )

    assessment = ControlAssessment(
        control_id=control.id,
        title=control.title,
        verdict=verdict,
        confidence=confidence,
        coverage_matched=matched,
        coverage_total=total,
        rationale=result.rationale,
        evidence=evidence,
        rejected_citations=rejected,
    )
    return assessment, used_config


def run_program(
    engagement: str,
    controls: list[Control],
    docs: dict[str, str],
    *,
    config: GatewayConfig | None = None,
    on_control=None,
) -> Workpaper:
    """Assess every control and assemble the workpaper.

    `on_control(i, total, assessment)` is called after each control for CLI
    progress reporting.
    """
    assessments: list[ControlAssessment] = []
    used_config = config
    for i, control in enumerate(controls, start=1):
        assessment, used_config = assess_control(control, docs, config=used_config)
        assessments.append(assessment)
        if on_control:
            on_control(i, len(controls), assessment)

    counts = Counter(a.verdict for a in assessments)
    errored = sum(1 for a in assessments if a.error)
    summary = {
        "total": len(assessments),
        "documented": counts.get("documented", 0),
        "partially_documented": counts.get("partially_documented", 0),
        "not_found": counts.get("not_found", 0),
        "errored": errored,
    }

    return Workpaper(
        engagement=engagement,
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        provider=used_config.provider if used_config else "unknown",
        model=used_config.model if used_config else "unknown",
        scope_note=SCOPE_NOTE,
        summary=summary,
        assessments=assessments,
        evidence_documents=docs,
    )
