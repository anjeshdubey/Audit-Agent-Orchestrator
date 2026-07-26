// Read-only workpaper viewer (Phase 1). Loads the workpaper JSON emitted by
// the CLI and renders each control; clicking one reveals the rationale and
// the cited passage highlighted inside the real source document.
//
// Rendering helpers (esc/normalize/renderDocWithHighlight/controlEl/summaryEl)
// live in render.js, shared with the Phase 2 live viewer (live.js).

function render(wp) {
  const app = document.getElementById("app");
  app.innerHTML = "";

  app.appendChild(summaryEl(wp.summary));

  const scope = document.createElement("div");
  scope.className = "scope-note";
  scope.textContent = wp.scope_note;
  app.appendChild(scope);

  const meta = document.createElement("div");
  meta.className = "meta";
  meta.textContent = `${wp.engagement} · generated ${wp.generated_at} · ${wp.provider}/${wp.model}`;
  app.appendChild(meta);

  wp.assessments.forEach((a) =>
    app.appendChild(controlEl(a, wp.evidence_documents || {}))
  );
}

fetch("data/workpaper.json")
  .then((r) => {
    if (!r.ok) throw new Error(`workpaper.json ${r.status}`);
    return r.json();
  })
  .then(render)
  .catch((e) => {
    document.getElementById("app").innerHTML =
      `<p class="none">Could not load data/workpaper.json (${esc(
        e.message
      )}). Run: <code>audit-orchestrator run</code></p>`;
  });
