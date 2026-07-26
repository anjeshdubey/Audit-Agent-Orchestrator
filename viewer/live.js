// Phase 2 live demo: starts a run on the server, streams its progress over
// SSE, and lets the visitor approve/reject any control the graph has routed
// to human review. Uses the same controlEl()/summaryEl() renderers as the
// static viewer (render.js) so a finished control looks identical either way.

let runId = null;
let source = null;
let docs = {};
let total = 0;

function logLine(text, cls) {
  const log = document.getElementById("log");
  const div = document.createElement("div");
  if (cls) div.className = cls;
  div.textContent = text;
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
}

function layout() {
  const app = document.getElementById("app");
  app.innerHTML = `
    <div id="summary-slot"></div>
    <div id="log" class="log-panel"></div>
    <div id="control-list"></div>
  `;
}

function upsertRow(assessment, stateClass) {
  const list = document.getElementById("control-list");
  const row = controlEl(assessment, docs);
  row.id = `row-${assessment.control_id}`;
  row.classList.add(stateClass);
  const existing = document.getElementById(row.id);
  if (existing) existing.replaceWith(row);
  else list.appendChild(row);
  return row;
}

function attachReviewPanel(row, controlId) {
  row.classList.add("open");
  const body = row.querySelector(".control-body");
  const panel = document.createElement("div");
  panel.className = "review-panel";
  panel.innerHTML = `
    <div class="label">This control needs your sign-off</div>
    <textarea placeholder="Optional note for the record"></textarea>
    <div class="review-actions">
      <button class="btn approve">Approve</button>
      <button class="btn reject">Reject</button>
    </div>
    <div class="decision-note"></div>
  `;
  body.appendChild(panel);

  const submit = async (action) => {
    panel.querySelectorAll("button").forEach((b) => (b.disabled = true));
    const note = panel.querySelector("textarea").value.trim() || null;
    const res = await fetch(
      `/api/runs/${runId}/controls/${encodeURIComponent(controlId)}/decision`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action, note }),
      }
    );
    if (!res.ok) {
      panel.querySelector(".decision-note").textContent =
        "Could not submit decision — try again.";
      panel.querySelectorAll("button").forEach((b) => (b.disabled = false));
      return;
    }
    panel.querySelector(".decision-note").textContent = "Submitted — waiting for the run to continue…";
  };

  panel.querySelector(".approve").addEventListener("click", () => submit("approve"));
  panel.querySelector(".reject").addEventListener("click", () => submit("reject"));
}

function handleEvent(ev) {
  switch (ev.type) {
    case "control_started": {
      total = ev.total;
      logLine(`[${ev.index + 1}/${ev.total}] ${ev.control_id} — extracting evidence…`);
      upsertRow(ev.assessment, "state-in-progress");
      break;
    }
    case "control_completed": {
      const a = ev.assessment;
      logLine(
        `  ✓ ${a.control_id} ${a.verdict} (conf ${a.confidence}, coverage ${a.coverage_matched}/${a.coverage_total}) — auto-approved`,
        "log-done"
      );
      upsertRow(a, "state-done");
      break;
    }
    case "review_pending": {
      const a = ev.assessment;
      logLine(
        `  ⚠ ${a.control_id} ${a.verdict} (conf ${a.confidence}) — routed to human review`,
        "log-review"
      );
      const row = upsertRow(a, "state-needs-review");
      attachReviewPanel(row, a.control_id);
      break;
    }
    case "control_finalized": {
      const a = ev.assessment;
      logLine(`  → ${a.control_id} finalized as ${a.verdict} by reviewer`, "log-done");
      upsertRow(a, "state-done");
      break;
    }
    case "run_complete": {
      logLine("Run complete.", "log-done");
      document.getElementById("summary-slot").replaceWith(summaryEl(ev.workpaper.summary));
      if (source) source.close();
      const btn = document.createElement("button");
      btn.className = "btn ghost";
      btn.textContent = "Run again";
      btn.addEventListener("click", start);
      document.getElementById("app").appendChild(btn);
      break;
    }
  }
}

async function start() {
  const app = document.getElementById("app");
  app.innerHTML = `<p class="loading">Starting engagement…</p>`;

  const startRes = await fetch("/api/runs", { method: "POST" });
  if (!startRes.ok) {
    const detail = await startRes.json().catch(() => ({}));
    app.innerHTML = `<p class="none">Could not start a run (${esc(
      detail.detail || startRes.status
    )}). If one is already running, wait for it to finish.</p>`;
    return;
  }
  ({ run_id: runId } = await startRes.json());

  const wp = await fetch(`/api/runs/${runId}/workpaper`).then((r) => r.json());
  docs = wp.evidence_documents || {};

  layout();
  const scope = document.createElement("div");
  scope.className = "scope-note";
  scope.textContent = wp.scope_note;
  document.getElementById("app").insertBefore(scope, document.getElementById("log"));

  source = new EventSource(`/api/runs/${runId}/events`);
  source.onmessage = (msg) => handleEvent(JSON.parse(msg.data));
  source.onerror = () => logLine("Connection to the run's event stream dropped.", "log-review");
}

document.getElementById("start").addEventListener("click", start);
