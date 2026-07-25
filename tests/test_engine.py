"""Tests for the engine's wiring: filtering, dedup, and failure resilience.

verify.py and scoring.py are tested directly elsewhere; this file tests how
engine.assess_control combines them with a model response, using a stubbed
extract_evidence so no real LLM call is made.
"""

from unittest.mock import patch

from audit_orchestrator.engine import assess_control, run_program
from audit_orchestrator.extraction import ExtractionResult, Finding
from audit_orchestrator.gateway import GatewayConfig
from audit_orchestrator.models import Citation, Control

DOCS = {"policy.md": "§1.1 MFA is required for all production access."}

CONTROL = Control(
    id="CC6.2",
    title="MFA",
    requirement="MFA is required for production access.",
    requirement_parts=["MFA is required", "applies to production access"],
    test_procedure="Confirm MFA is required for production.",
)

CONFIG = GatewayConfig(provider="stub", auth_token="x", model="stub-model")


def _finding(part: str, quote: str) -> Finding:
    return Finding(
        requirement_part=part,
        citation=Citation(source="policy.md", anchor="§1.1", exact_quote=quote),
    )


def _stub(result: ExtractionResult):
    return patch(
        "audit_orchestrator.engine.extract_evidence",
        return_value=(result, CONFIG),
    )


def test_full_coverage_with_two_verified_findings_is_documented():
    result = ExtractionResult(
        findings=[
            _finding("MFA is required", "MFA is required for all production access"),
            _finding("applies to production access", "for all production access"),
        ],
        rationale="Both parts covered.",
    )
    with _stub(result):
        a, _ = assess_control(CONTROL, DOCS, config=CONFIG)
    assert a.verdict == "documented"
    assert a.coverage_matched == 2
    assert a.error is None


def test_unfabricated_but_unverifiable_quote_is_rejected_not_counted():
    result = ExtractionResult(
        findings=[
            _finding("MFA is required", "MFA is required for all production access"),
            _finding("applies to production access", "this text is not in the doc"),
        ],
        rationale="One real, one fabricated.",
    )
    with _stub(result):
        a, _ = assess_control(CONTROL, DOCS, config=CONFIG)
    assert a.verdict == "partially_documented"
    assert a.coverage_matched == 1
    assert a.rejected_citations == 1


def test_finding_for_unknown_requirement_part_is_ignored():
    result = ExtractionResult(
        findings=[
            _finding("a part the control never declared", "MFA is required for all")
        ],
        rationale="Model invented a part.",
    )
    with _stub(result):
        a, _ = assess_control(CONTROL, DOCS, config=CONFIG)
    assert a.verdict == "not_found"
    assert a.coverage_matched == 0


def test_duplicate_findings_for_same_part_count_once():
    result = ExtractionResult(
        findings=[
            _finding("MFA is required", "MFA is required for all production access"),
            _finding("MFA is required", "MFA is required for all production access"),
        ],
        rationale="Duplicate finding.",
    )
    with _stub(result):
        a, _ = assess_control(CONTROL, DOCS, config=CONFIG)
    assert a.coverage_matched == 1
    assert a.verdict == "partially_documented"


def test_extraction_failure_does_not_crash_and_is_marked_errored():
    with patch(
        "audit_orchestrator.engine.extract_evidence",
        side_effect=RuntimeError("429 rate limit"),
    ):
        a, used_config = assess_control(CONTROL, DOCS, config=CONFIG)
    assert a.error is not None
    assert "429 rate limit" in a.error
    assert a.verdict == "not_found"
    assert a.confidence == 0.0


def test_run_program_continues_past_one_failed_control():
    """The core resilience guarantee: one control's transient failure must not
    discard the assessments already completed for the others."""
    ok_result = ExtractionResult(
        findings=[
            _finding("MFA is required", "MFA is required for all production access"),
            _finding("applies to production access", "for all production access"),
        ],
        rationale="ok",
    )

    calls = {"n": 0}

    def flaky_extract(control, docs, *, config=None):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("simulated transient failure")
        return ok_result, CONFIG

    controls = [CONTROL, CONTROL, CONTROL]
    with patch("audit_orchestrator.engine.extract_evidence", side_effect=flaky_extract):
        wp = run_program("test-engagement", controls, DOCS, config=CONFIG)

    assert wp.summary["total"] == 3
    assert wp.summary["errored"] == 1
    assert wp.summary["documented"] == 2
    assert wp.assessments[1].error is not None
