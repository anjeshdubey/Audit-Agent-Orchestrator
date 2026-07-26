"""The live engagement graph — Phase 2's LangGraph port of the Phase 1 loop.

`engine.assess_control()` already does retrieve -> extract -> verify -> score
as one deterministic function (model proposes, code disposes) and is reused
here unchanged rather than reimplemented across graph nodes. What the graph
adds is the ability to *pause mid-run*: a control that isn't a clean,
high-confidence `documented` verdict is routed to a human-in-the-loop gate via
LangGraph's `interrupt()`, and the run only continues once a reviewer
approves or rejects it (`Command(resume=...)`), instead of the Phase 1
CLI's blind straight-through loop.

    assess -> [route] -> finalize -> [loop back to assess, or END]
                 |-> hitl -> finalize

`assess` is the only node that talks to a model; `hitl` and `finalize` are
pure state transitions.
"""

from __future__ import annotations

from typing import Any, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import interrupt

from .engine import assess_control
from .gateway import GatewayConfig
from .models import Control, ControlAssessment

# A control only auto-completes without a human gate if it's a clean,
# high-confidence pass. Anything else -- partial, not-found, an errored
# extraction -- is exactly the "uncertain or failing" set the product vision
# says must land in front of a reviewer.
AUTO_APPROVE_VERDICT = "documented"
AUTO_APPROVE_CONFIDENCE = 0.85


class RunState(TypedDict):
    engagement: str
    controls: list[Control]
    docs: dict[str, str]
    index: int
    assessments: list[ControlAssessment]
    gateway_config: GatewayConfig | None
    current: ControlAssessment | None
    current_decision: dict[str, Any] | None


def needs_review(assessment: ControlAssessment) -> bool:
    if assessment.error:
        return True
    return not (
        assessment.verdict == AUTO_APPROVE_VERDICT
        and assessment.confidence >= AUTO_APPROVE_CONFIDENCE
    )


def assess_node(state: RunState) -> dict:
    control = state["controls"][state["index"]]
    assessment, used_config = assess_control(
        control, state["docs"], config=state["gateway_config"]
    )
    return {"current": assessment, "gateway_config": used_config}


def route_after_assess(state: RunState) -> str:
    return "hitl" if needs_review(state["current"]) else "finalize"


def hitl_node(state: RunState) -> dict:
    """Pause for a human decision. On resume, `decision` is whatever value the
    caller passed via `Command(resume=decision)` -- {"action": "approve" |
    "reject", "note": str | None}.

    A rejection overrides the verdict rather than discarding the assessment:
    the evidence and rationale stay visible, but the control can no longer
    read as a pass. This mirrors "the human always concludes" -- the agent's
    proposal is what gets overruled, not erased.
    """
    assessment = state["current"]
    decision = interrupt(
        {"control_id": assessment.control_id, "assessment": assessment.model_dump()}
    )
    action = decision.get("action", "approve")
    note = decision.get("note")
    if action == "reject":
        assessment = assessment.model_copy(
            update={
                "verdict": "not_found",
                "rationale": f"Rejected by reviewer: {note or 'no reason given'}",
            }
        )
    return {"current": assessment, "current_decision": {"action": action, "note": note}}


def finalize_node(state: RunState) -> dict:
    return {
        "assessments": [*state["assessments"], state["current"]],
        "index": state["index"] + 1,
        "current": None,
        "current_decision": None,
    }


def route_after_finalize(state: RunState) -> str:
    return END if state["index"] >= len(state["controls"]) else "assess"


def build_graph() -> StateGraph:
    graph = StateGraph(RunState)
    graph.add_node("assess", assess_node)
    graph.add_node("hitl", hitl_node)
    graph.add_node("finalize", finalize_node)
    graph.set_entry_point("assess")
    graph.add_conditional_edges(
        "assess", route_after_assess, {"hitl": "hitl", "finalize": "finalize"}
    )
    graph.add_edge("hitl", "finalize")
    graph.add_conditional_edges(
        "finalize", route_after_finalize, {END: END, "assess": "assess"}
    )
    return graph


def compile_graph(checkpointer: MemorySaver | None = None) -> CompiledStateGraph:
    return build_graph().compile(checkpointer=checkpointer or MemorySaver())


def initial_state(
    engagement: str, controls: list[Control], docs: dict[str, str]
) -> RunState:
    return {
        "engagement": engagement,
        "controls": controls,
        "docs": docs,
        "index": 0,
        "assessments": [],
        "gateway_config": None,
        "current": None,
        "current_decision": None,
    }
