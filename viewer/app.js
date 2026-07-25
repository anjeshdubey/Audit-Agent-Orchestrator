// Read-only workpaper viewer. Loads the workpaper JSON emitted by the CLI and
// renders each control; clicking one reveals the rationale and the cited
// passage highlighted inside the real source document.

const VERDICT_LABEL = {
  documented: "Documented",
  partially_documented: "Partially documented",
  not_found: "Not found",
};

function esc(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

// Normalize the way verify.py does (collapse whitespace, lowercase) so the
// highlight lands on the same span the backend verified.
function normalize(s) {
  return s.replace(/\s+/g, " ").trim().toLowerCase();
}

// Render a source document with the cited quote wrapped in <mark>. Matching is
// whitespace/case-insensitive to mirror backend verification.
function renderDocWithHighlight(docText, quote) {
  if (!quote) return esc(docText);
  const normDoc = normalize(docText);
  const normQuote = normalize(quote);
  const idx = normDoc.indexOf(normQuote);
  if (idx === -1) return esc(docText); // shouldn't happen for verified quotes

  // Map the normalized match back to raw offsets by walking the raw string.
  let rawStart = -1;
  let rawEnd = -1;
  let normPos = 0;
  let prevSpace = false;
  for (let i = 0; i < docText.length; i++) {
    const ch = docText[i];
    const isSpace = /\s/.test(ch);
    let normCh;
    if (isSpace) {
      if (prevSpace) {
        continue;
      }
      normCh = " ";
      prevSpace = true;
    } else {
      normCh = ch.toLowerCase();
      prevSpace = false;
    }
    // Account for leading trim: skip counting a leading space.
    if (normPos === 0 && normCh === " ") continue;
    if (normPos === idx && rawStart === -1) rawStart = i;
    normPos += normCh.length;
    if (normPos === idx + normQuote.length) {
      rawEnd = i + 1;
      break;
    }
  }
  if (rawStart === -1 || rawEnd === -1) return esc(docText);
  return (
    esc(docText.slice(0, rawStart)) +
    "<mark>" +
    esc(docText.slice(rawStart, rawEnd)) +
    "</mark>" +
    esc(docText.slice(rawEnd))
  );
}

function controlEl(a, docs) {
  const el = document.createElement("div");
  el.className = "control";

  const cov = a.coverage_total
    ? Math.round((a.coverage_matched / a.coverage_total) * 100)
    : 0;

  let citationHtml;
  if (a.evidence && a.evidence.length) {
    const items = a.evidence
      .map((item) => {
        const c = item.citation;
        const doc = docs[c.source] || "";
        return `
          <div class="evidence-item">
            <div class="evidence-part">${esc(item.requirement_part)}</div>
            <div class="citation-box">
              <div class="citation-src">${esc(c.source)} · ${esc(c.anchor)}</div>
              <div class="doc-render">${renderDocWithHighlight(
                doc,
                c.exact_quote
              )}</div>
            </div>
          </div>`;
      })
      .join("");
    citationHtml = `<div class="field"><div class="label">Evidence — each part verified in source</div>${items}</div>`;
  } else {
    citationHtml = `<div class="field"><div class="label">Evidence</div><div class="none">None — no verified supporting passage in the documents.</div></div>`;
  }

  const rejectedHtml = a.rejected_citations
    ? `<div class="field"><div class="rejected">${a.rejected_citations} proposed citation(s) rejected — quote not found in source (fabrication caught).</div></div>`
    : "";

  el.innerHTML = `
    <div class="control-head">
      <span class="dot ${a.verdict}"></span>
      <span class="cid">${esc(a.control_id)}</span>
      <span class="ctitle">${esc(a.title)}</span>
      <span class="verdict-label">${VERDICT_LABEL[a.verdict]}</span>
      <span class="conf">conf ${a.confidence}</span>
      <span class="chev">▶</span>
    </div>
    <div class="control-body">
      <div class="field">
        <div class="label">Coverage — ${a.coverage_matched}/${
    a.coverage_total
  } requirement parts</div>
        <div class="coverage-bar"><div class="coverage-fill" style="width:${cov}%"></div></div>
      </div>
      <div class="field">
        <div class="label">Rationale</div>
        <div>${esc(a.rationale)}</div>
      </div>
      ${citationHtml}
      ${rejectedHtml}
    </div>`;

  el.querySelector(".control-head").addEventListener("click", () => {
    el.classList.toggle("open");
  });
  return el;
}

function render(wp) {
  const app = document.getElementById("app");
  app.innerHTML = "";
  const s = wp.summary;

  const summary = document.createElement("div");
  summary.className = "summary";
  summary.innerHTML = `
    <span class="pill documented">Documented <b>${s.documented}</b></span>
    <span class="pill partial">Partial <b>${s.partially_documented}</b></span>
    <span class="pill notfound">Not found <b>${s.not_found}</b></span>
    <span class="pill">Total <b>${s.total}</b></span>`;
  app.appendChild(summary);

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
