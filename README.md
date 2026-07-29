# audit-orchestrator

**[Try the live demo →](https://anjeshdubey.github.io/Audit-Agent-Orchestrator/)**
Static viewer on GitHub Pages, real LLM calls on a Modal-hosted API — see
[Deploying](#deploying) for how the two are wired together.

A grounded, human-in-the-loop agent for **compliance evidence review**. Give it
a list of controls (a SOC 2-style checklist) and a set of policy documents, and
it answers each control with a **verdict, a confidence score, and a citation to
the exact source passage** it relied on — routing anything uncertain to a human
to sign off. Nothing is ever concluded without a person, and no answer is
trusted unless its supporting quote can be verified against the source.

I built this because the interesting engineering problem in applied AI isn't
getting a model to produce an answer — it's making that answer **traceable and
trustworthy** enough that a domain expert would stake their name on it. Compliance
review is a clean forcing function for that: the answer is worthless without a
verifiable citation, and a wrong "pass" is worse than no answer at all.

## Design principles

- **The human always concludes.** The agent proposes; a person disposes. No
  control is marked passed or failed without explicit sign-off.
- **Verification before confidence.** The primary guardrail is deterministic:
  a cited passage must literally exist in the source, checked in code — not by
  asking the model how sure it is. A confident but fabricated citation is
  caught by the quote check, not the score.
- **Confidence is derived, not self-reported.** The score comes from signals
  the code owns (did verification pass, how much of the requirement the
  evidence covers), so it means something.
- **Predictable over clever.** In this domain a repeatable correct answer beats
  an impressive-looking wrong one.

## Scope

This does **design/documentation testing** — "is this control adequately
documented, and where's the proof?" It deliberately does *not* do sample-based
operating-effectiveness testing. Design testing maps cleanly onto grounded
document extraction, which is the capability this project is about.

## How it works

Per control, the agent:

1. **Extracts evidence** — for each part of the requirement it believes is met,
   the model returns a *verbatim* citation (source · section · exact quote).
2. **Verifies** — code checks each quoted passage literally exists in the named
   source. An unverifiable quote is rejected and cannot count.
3. **Scores in code** — the verdict (`documented` / `partially_documented` /
   `not_found`) and a confidence score are derived from verification + how many
   requirement parts are backed by verified evidence. The model never reports
   its own verdict or confidence.

Verification proves a citation is *authentic*, not that it's *relevant* — the
semantic-sufficiency judgment is surfaced for a human reviewer (the
human-in-the-loop phase), which is the whole point: the agent does the tedious
first pass, a person signs off.

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e '.[anthropic]'     # or .[groq] / .[gemini] / .[together] / .[all]
cp .env.example .env              # set at least one provider key

# Run the bundled Northwind sample engagement (12 controls, 5 policy docs)
audit-orchestrator run --markdown out/workpaper.md

# View the workpaper (served, not file://, so the browser can fetch the JSON)
python -m http.server -d viewer 8000   # then open http://localhost:8000
```

Run the deterministic-core tests with `pip install -e '.[dev]' && pytest`.

### Phase 2 — the live demo

```bash
pip install -e '.[anthropic,server]'   # adds fastapi/uvicorn/langgraph
cp .env.example .env                   # set at least one provider key

audit-orchestrator serve               # http://localhost:8000
```

Open `http://localhost:8000` and click **Start engagement**. Every
control streams in over SSE as it's assessed; anything short of a clean,
high-confidence `documented` verdict (partial, not-found, or an errored
extraction) pauses the run at a real LangGraph `interrupt()` and drops into a
review panel — approve or reject it, with an optional note, and the run
resumes from exactly there. This is one `uvicorn` process serving both the
API and the viewer, driving real LLM calls against whichever provider is
configured in `.env`; only one run at a time.

The event log next to the control list shows the real pipeline steps
(extract → verify → score) as they happen — it is **not** simulated
token-by-token model "thinking." The extraction call itself isn't streamed
(it's a single structured-output request), so nothing in the live view is
dramatized beyond what actually occurred.

`http://localhost:8000/workpaper.html` still serves the original Phase 1
static, read-only viewer over a frozen `workpaper.json` — unaffected by the
live server.

## Deploying

The public demo splits the single local process across two hosts, since
GitHub Pages only serves static files and can't run the FastAPI/LangGraph
backend:

```
anjeshdubey.github.io/Audit-Agent-Orchestrator/  (viewer/, static)
        │  fetch + SSE, cross-origin (CORS)
        ▼
*.modal.run  (FastAPI + LangGraph, single pinned container)
```

- **API → Modal.** `modal_app.py` runs `audit_orchestrator.server:app` as a
  Modal ASGI web endpoint, pinned to `max_containers=1` — the server keeps
  run state (`RUNS`, `_active_run_id`) in a process-global dict, so a second
  container would silently split traffic and corrupt whichever engagement a
  browser is watching. Provider keys live in a Modal Secret, not the image:
  ```bash
  modal secret create audit-orchestrator-secrets --from-dotenv .env --force
  modal deploy modal_app.py
  ```
  Redeploy after any change under `src/`, `sample/`, or `viewer/` (the image
  bundles all three) — a redeploy also resets any stuck in-memory run state.

- **Viewer → GitHub Pages.** `.github/workflows/pages.yml` publishes
  `viewer/` to Pages on every push to `main` that touches it. `viewer/config.js`
  picks the API base URL at load time: relative paths (same-origin) on
  `localhost`/`127.0.0.1`, the Modal URL everywhere else — including the
  `anjesh.ai` custom domain GitHub cascades to project-page subpaths.
  `server.py`'s `DEFAULT_ALLOWED_ORIGINS` CORS list has to match; override or
  extend it with a comma-separated `ALLOWED_ORIGINS` env var on the Modal
  function without a code change.

- Only one engagement runs at a time, globally, across every visitor — by
  design, matching the rest of this project's no-DB, no-multi-tenant posture.
  A second visitor mid-run gets a 409 until the first run finishes.

## Status

Phase 1 (testing-agent core) and Phase 2 (live HITL review loop) are both
working end-to-end. Phase 1: a CLI runs a full control program against an
evidence set and emits a workpaper (JSON + Markdown) with verified
citations, plus a read-only viewer that highlights each cited passage inside
its source document. Phase 2: the same deterministic assess/verify/score
core, ported into a LangGraph state machine with `MemorySaver` checkpointing,
driven live over SSE, with a genuine interrupt/resume gate for human
approve/reject decisions. The earlier `spike/phase_0_5.py` remains as the
original proof of the core loop.

All sample data is synthetic and clearly fictional — never real client data.
