"""FastAPI server for the Phase 2 live engagement demo.

Drives the graph.py state machine live: each control's result streams to the
browser over SSE as soon as it's ready, and any control that needs a human
decision genuinely pauses the graph (a real LangGraph interrupt, not a
simulated delay) until the browser's Approve/Reject click resumes it via
`Command(resume=...)`.

Single-process, in-memory, single-active-run demo -- matches the rest of the
project's no-DB, no-multi-tenant posture. Not meant to survive a restart or
serve concurrent engagements.
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command
from pydantic import BaseModel

# Origins allowed to call the API cross-origin -- the GitHub Pages viewer is
# served from a different origin than this API when deployed on Modal.
# Override/extend with a comma-separated ALLOWED_ORIGINS env var.
DEFAULT_ALLOWED_ORIGINS = [
    "https://anjeshdubey.github.io",
    "https://anjesh.ai",
    "http://anjesh.ai",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

from .engine import assemble_workpaper
from .gateway import GatewayConfig
from .graph import compile_graph, initial_state
from .models import Control, ControlAssessment, Workpaper
from .program import load_evidence, load_program

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROGRAM = REPO_ROOT / "sample/northwind/program.yaml"
DEFAULT_EVIDENCE = REPO_ROOT / "sample/northwind/evidence"
VIEWER_DIR = REPO_ROOT / "viewer"


@dataclass
class Run:
    run_id: str
    engagement: str
    controls: list[Control]
    docs: dict[str, str]
    graph: CompiledStateGraph
    thread: dict[str, Any]
    events: list[dict] = field(default_factory=list)
    subscribers: list[asyncio.Queue] = field(default_factory=list)
    assessments: list[ControlAssessment] = field(default_factory=list)
    gateway_config: GatewayConfig | None = None
    pending_control_id: str | None = None
    pending_decision: "asyncio.Future | None" = None


class Decision(BaseModel):
    action: Literal["approve", "reject"]
    note: str | None = None


RUNS: dict[str, Run] = {}
_active_run_id: str | None = None


def _emit(run: Run, event: dict) -> None:
    run.events.append(event)
    for q in run.subscribers:
        q.put_nowait(event)


def _build_workpaper(run: Run) -> Workpaper:
    return assemble_workpaper(
        run.engagement,
        run.controls,
        run.docs,
        run.assessments,
        config=run.gateway_config,
    )


async def _drive_run(run: Run) -> None:
    global _active_run_id
    total = len(run.controls)
    payload: Any = initial_state(run.engagement, run.controls, run.docs)
    reviewed_control_id: str | None = None

    try:
        while True:
            async for chunk in run.graph.astream(
                payload, config=run.thread, stream_mode="updates"
            ):
                if "assess" in chunk:
                    assessment: ControlAssessment = chunk["assess"]["current"]
                    run.gateway_config = chunk["assess"]["gateway_config"]
                    index = run.graph.get_state(run.thread).values["index"]
                    _emit(
                        run,
                        {
                            "type": "control_started",
                            "control_id": assessment.control_id,
                            "index": index,
                            "total": total,
                            "assessment": assessment.model_dump(),
                        },
                    )
                elif "__interrupt__" in chunk:
                    data = chunk["__interrupt__"][0].value
                    reviewed_control_id = data["control_id"]
                    run.pending_control_id = reviewed_control_id
                    _emit(run, {"type": "review_pending", **data})
                elif "finalize" in chunk:
                    assessments = chunk["finalize"]["assessments"]
                    run.assessments = assessments
                    finished = assessments[-1]
                    was_reviewed = reviewed_control_id == finished.control_id
                    reviewed_control_id = None
                    _emit(
                        run,
                        {
                            "type": (
                                "control_finalized"
                                if was_reviewed
                                else "control_completed"
                            ),
                            "assessment": finished.model_dump(),
                        },
                    )

            if not run.graph.get_state(run.thread).next:
                break  # graph reached END

            loop = asyncio.get_running_loop()
            run.pending_decision = loop.create_future()
            decision = await run.pending_decision
            run.pending_decision = None
            run.pending_control_id = None
            payload = Command(resume=decision)
    finally:
        _emit(
            run,
            {"type": "run_complete", "workpaper": _build_workpaper(run).model_dump()},
        )
        if _active_run_id == run.run_id:
            _active_run_id = None


app = FastAPI(title="Audit Orchestrator — Live Demo")

_extra_origins = [
    o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=DEFAULT_ALLOWED_ORIGINS + _extra_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.post("/api/runs")
async def start_run() -> dict:
    global _active_run_id
    if _active_run_id is not None:
        raise HTTPException(409, "A run is already in progress.")

    run_id = uuid.uuid4().hex[:12]
    controls = load_program(DEFAULT_PROGRAM)
    docs = load_evidence(DEFAULT_EVIDENCE)
    run = Run(
        run_id=run_id,
        engagement=DEFAULT_EVIDENCE.name,
        controls=controls,
        docs=docs,
        graph=compile_graph(MemorySaver()),
        thread={"configurable": {"thread_id": run_id}},
    )
    RUNS[run_id] = run
    _active_run_id = run_id
    asyncio.create_task(_drive_run(run))
    return {"run_id": run_id}


async def _event_stream(run: Run):
    queue: asyncio.Queue = asyncio.Queue()
    already = list(run.events)
    run.subscribers.append(queue)
    try:
        for event in already:
            yield f"data: {json.dumps(event)}\n\n"
            if event["type"] == "run_complete":
                return
        while True:
            event = await queue.get()
            yield f"data: {json.dumps(event)}\n\n"
            if event["type"] == "run_complete":
                return
    finally:
        run.subscribers.remove(queue)


@app.get("/api/runs/{run_id}/events")
async def run_events(run_id: str) -> StreamingResponse:
    run = RUNS.get(run_id)
    if run is None:
        raise HTTPException(404, "Unknown run.")
    return StreamingResponse(_event_stream(run), media_type="text/event-stream")


@app.post("/api/runs/{run_id}/controls/{control_id}/decision")
async def submit_decision(run_id: str, control_id: str, decision: Decision) -> dict:
    run = RUNS.get(run_id)
    if run is None:
        raise HTTPException(404, "Unknown run.")
    if run.pending_decision is None or run.pending_control_id != control_id:
        raise HTTPException(409, f"No pending decision for control {control_id}.")
    run.pending_decision.set_result(decision.model_dump())
    return {"ok": True}


@app.get("/api/runs/{run_id}/workpaper")
async def get_workpaper(run_id: str) -> dict:
    run = RUNS.get(run_id)
    if run is None:
        raise HTTPException(404, "Unknown run.")
    return _build_workpaper(run).model_dump()


# Serves the Phase 2 live page (index.html/live.js) and the Phase 1 static
# viewer (workpaper.html/app.js) from the same process as the API -- one
# port, no CORS. Mounted last so it doesn't shadow the /api routes above.
app.mount("/", StaticFiles(directory=str(VIEWER_DIR), html=True), name="viewer")
