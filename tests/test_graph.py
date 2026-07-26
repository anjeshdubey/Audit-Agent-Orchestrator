"""Tests for the Phase 2 live graph: routing to human review and resuming.

Uses the same stubbed-`extract_evidence` pattern as test_engine.py, so no
real LLM call is made and the deterministic verify/score core is exercised
exactly as it is in the CLI path -- the graph only adds the pause/resume
plumbing around `engine.assess_control`.
"""

from unittest.mock import patch

from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from audit_orchestrator.extraction import ExtractionResult, Finding
from audit_orchestrator.gateway import GatewayConfig
from audit_orchestrator.graph import compile_graph, initial_state
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


FULL_COVERAGE = ExtractionResult(
    findings=[
        _finding("MFA is required", "MFA is required for all production access"),
        _finding("applies to production access", "for all production access"),
    ],
    rationale="Both parts covered.",
)

PARTIAL_COVERAGE = ExtractionResult(
    findings=[
        _finding("MFA is required", "MFA is required for all production access"),
    ],
    rationale="Only one part covered.",
)


def _run_graph(controls):
    graph = compile_graph(MemorySaver())
    thread = {"configurable": {"thread_id": "test-run"}}
    state = initial_state("test-engagement", controls, DOCS)
    return graph, thread, graph.invoke(state, config=thread)


def test_clean_documented_control_auto_finalizes_without_interrupt():
    with _stub(FULL_COVERAGE):
        _, _, result = _run_graph([CONTROL])
    assert result["assessments"][0].verdict == "documented"
    assert result["index"] == 1


def test_partial_control_interrupts_for_human_review():
    with _stub(PARTIAL_COVERAGE):
        _, _, result = _run_graph([CONTROL])
    # The graph paused instead of finishing -- no assessments appended yet.
    assert result["assessments"] == []
    assert "__interrupt__" in result
    payload = result["__interrupt__"][0].value
    assert payload["control_id"] == "CC6.2"
    assert payload["assessment"]["verdict"] == "partially_documented"


def test_approve_resumes_and_keeps_the_proposed_verdict():
    with _stub(PARTIAL_COVERAGE):
        graph, thread, _ = _run_graph([CONTROL])
        result = graph.invoke(Command(resume={"action": "approve"}), config=thread)
    assert result["assessments"][0].verdict == "partially_documented"
    assert result["index"] == 1


def test_reject_resumes_and_overrides_the_verdict():
    with _stub(PARTIAL_COVERAGE):
        graph, thread, _ = _run_graph([CONTROL])
        result = graph.invoke(
            Command(resume={"action": "reject", "note": "quote too weak"}),
            config=thread,
        )
    assert result["assessments"][0].verdict == "not_found"
    assert "quote too weak" in result["assessments"][0].rationale


def test_multi_control_run_continues_past_a_reviewed_control():
    with _stub(PARTIAL_COVERAGE):
        graph, thread, first = _run_graph([CONTROL, CONTROL])
        assert "__interrupt__" in first
        result = graph.invoke(Command(resume={"action": "approve"}), config=thread)
    # Second control is identical evidence, so it also needs review -- confirm
    # the loop reached it rather than stopping after the first interrupt.
    assert "__interrupt__" in result
    assert result["index"] == 1
