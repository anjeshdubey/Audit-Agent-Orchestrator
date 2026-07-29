// Phase 3 upload UI — document intake form.
//
// Flow:
//   1. User fills in engagement name + one or more documents (paste or drag-drop file).
//   2. "Upload documents" POSTs to POST /intake.
//   3. On success, shows the result panel with:
//      - Batch intake_id
//      - Per-document IDs (with titles)
//      - Ready-to-paste CLI command
//      - "Start live assessment" button (POSTs /api/runs, then opens index.html)

const MAX_BYTES = 1_048_576; // must match server MAX_DOCUMENT_BYTES

// ── Document slot management ────────────────────────────────────────────────

let docCount = 0;

function makeDocSlot() {
  docCount++;
  const idx = docCount;
  const slot = document.createElement("div");
  slot.className = "doc-slot";
  slot.dataset.idx = idx;

  slot.innerHTML = `
    <div class="doc-slot-header">
      <span class="doc-number">Doc ${idx}</span>
      <input
        class="text-input doc-title-input"
        type="text"
        placeholder="Document title (e.g. Access Control Policy)"
        autocomplete="off"
        spellcheck="false"
        id="doc-title-${idx}"
      />
      <button class="remove-btn" title="Remove document" aria-label="Remove document ${idx}">✕</button>
    </div>

    <div class="drop-zone" id="drop-zone-${idx}">
      <textarea
        class="doc-textarea"
        placeholder="Paste policy text here…"
        id="doc-text-${idx}"
        aria-label="Document text for doc ${idx}"
      ></textarea>
      <div class="drop-overlay">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M12 16V8m0 0-3 3m3-3 3 3" stroke-linecap="round" stroke-linejoin="round"/>
          <path d="M20.25 16.5A4.75 4.75 0 0 0 17.5 7.5h-.95A7.5 7.5 0 1 0 3.75 15" stroke-linecap="round"/>
        </svg>
        <span>Drop a .txt or .md file here, or paste text above</span>
      </div>
    </div>
    <div class="char-count" id="char-count-${idx}">0 / 1 MB</div>
    <div class="file-row" id="file-row-${idx}"></div>
    <div class="inline-error" id="err-title-${idx}">Title is required.</div>
    <div class="inline-error" id="err-text-${idx}">Document text is required.</div>
  `;

  // Remove button
  slot.querySelector(".remove-btn").addEventListener("click", () => {
    slot.remove();
    renumberSlots();
  });

  // Char counter
  const textarea = slot.querySelector(".doc-textarea");
  const counter  = slot.querySelector(`#char-count-${idx}`);
  textarea.addEventListener("input", () => {
    updateCharCount(textarea, counter);
    if (textarea.value.trim()) {
      slot.querySelector(`#drop-zone-${idx}`).classList.add("has-content");
    } else {
      slot.querySelector(`#drop-zone-${idx}`).classList.remove("has-content");
    }
  });

  // Drag-and-drop
  const dropZone = slot.querySelector(`#drop-zone-${idx}`);
  dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropZone.classList.add("drag-over");
  });
  dropZone.addEventListener("dragleave", () => dropZone.classList.remove("drag-over"));
  dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropZone.classList.remove("drag-over");
    const file = e.dataTransfer.files[0];
    if (file) loadFile(file, slot, idx);
  });

  return slot;
}

function renumberSlots() {
  document.querySelectorAll(".doc-slot").forEach((slot, i) => {
    slot.querySelector(".doc-number").textContent = `Doc ${i + 1}`;
  });
}

function updateCharCount(textarea, counter) {
  const bytes = new TextEncoder().encode(textarea.value).length;
  const pct   = bytes / MAX_BYTES;
  const label = bytes < 1024
    ? `${bytes} B`
    : bytes < 1_048_576
    ? `${(bytes / 1024).toFixed(1)} KB`
    : `${(bytes / MAX_BYTES).toFixed(2)} MB`;

  counter.textContent = `${label} / 1 MB`;
  counter.className = "char-count" + (pct > 1 ? " over" : pct > 0.8 ? " warn" : "");
}

function loadFile(file, slot, idx) {
  const allowed = [".txt", ".md"];
  const ok = allowed.some((ext) => file.name.toLowerCase().endsWith(ext));
  if (!ok) {
    setStatus(`Only .txt and .md files are supported (got "${file.name}").`, "error");
    return;
  }
  const reader = new FileReader();
  reader.onload = (e) => {
    const textarea = slot.querySelector(`#doc-text-${idx}`);
    const counter  = slot.querySelector(`#char-count-${idx}`);
    const dropZone = slot.querySelector(`#drop-zone-${idx}`);
    const fileRow  = slot.querySelector(`#file-row-${idx}`);
    const titleInput = slot.querySelector(`#doc-title-${idx}`);

    textarea.value = e.target.result;
    dropZone.classList.add("has-content");
    updateCharCount(textarea, counter);

    // Auto-fill title from filename if title is empty
    if (!titleInput.value.trim()) {
      titleInput.value = file.name.replace(/\.(txt|md)$/i, "").replace(/[-_]/g, " ");
    }

    // File pill
    fileRow.innerHTML = "";
    const pill = document.createElement("span");
    pill.className = "file-pill";
    pill.innerHTML = `
      <svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor">
        <path d="M4 0a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V5.5L9.5 0H4zm5 1.5V5h3.5L9 1.5z"/>
      </svg>
      ${esc(file.name)}
      <button title="Clear file" aria-label="Clear file">✕</button>
    `;
    pill.querySelector("button").addEventListener("click", () => {
      textarea.value = "";
      dropZone.classList.remove("has-content");
      updateCharCount(textarea, counter);
      fileRow.innerHTML = "";
    });
    fileRow.appendChild(pill);
  };
  reader.readAsText(file);
}

// ── Validation ──────────────────────────────────────────────────────────────

function validateForm() {
  let valid = true;

  // Engagement
  const engInput = document.getElementById("engagement-input");
  const engErr   = document.getElementById("err-engagement");
  if (!engInput.value.trim()) {
    engInput.classList.add("invalid");
    if (engErr) { engErr.textContent = "Engagement name is required."; engErr.classList.add("visible"); }
    valid = false;
  } else {
    engInput.classList.remove("invalid");
    if (engErr) engErr.classList.remove("visible");
  }

  // Documents
  const slots = document.querySelectorAll(".doc-slot");
  if (!slots.length) {
    setStatus("Add at least one document before uploading.", "error");
    return false;
  }

  const titles = new Set();
  slots.forEach((slot) => {
    const idx       = slot.dataset.idx;
    const titleEl   = slot.querySelector(`#doc-title-${idx}`);
    const textEl    = slot.querySelector(`#doc-text-${idx}`);
    const errTitle  = slot.querySelector(`#err-title-${idx}`);
    const errText   = slot.querySelector(`#err-text-${idx}`);

    const title = titleEl.value.trim();
    const text  = textEl.value.trim();
    const bytes = new TextEncoder().encode(textEl.value).length;

    // Title
    if (!title) {
      titleEl.classList.add("invalid");
      errTitle.classList.add("visible");
      valid = false;
    } else if (titles.has(title.toLowerCase())) {
      titleEl.classList.add("invalid");
      errTitle.textContent = "Duplicate title — each document must have a unique title.";
      errTitle.classList.add("visible");
      valid = false;
    } else {
      titleEl.classList.remove("invalid");
      errTitle.classList.remove("visible");
      titles.add(title.toLowerCase());
    }

    // Text
    if (!text) {
      textEl.classList.add("invalid");
      errText.textContent = "Document text is required.";
      errText.classList.add("visible");
      valid = false;
    } else if (bytes > MAX_BYTES) {
      textEl.classList.add("invalid");
      errText.textContent = `Document exceeds 1 MB limit (${(bytes / MAX_BYTES).toFixed(2)} MB).`;
      errText.classList.add("visible");
      valid = false;
    } else {
      textEl.classList.remove("invalid");
      errText.classList.remove("visible");
    }
  });

  return valid;
}

// ── Upload ──────────────────────────────────────────────────────────────────

function setStatus(msg, cls = "") {
  const el = document.getElementById("upload-status");
  el.className = cls;
  el.innerHTML = msg;
}

async function upload() {
  if (!validateForm()) return;

  const engagement = document.getElementById("engagement-input").value.trim();
  const apiKey     = document.getElementById("api-key-input").value;

  const documents = [];
  document.querySelectorAll(".doc-slot").forEach((slot) => {
    const idx = slot.dataset.idx;
    documents.push({
      title: slot.querySelector(`#doc-title-${idx}`).value.trim(),
      text:  slot.querySelector(`#doc-text-${idx}`).value,
    });
  });

  const uploadBtn = document.getElementById("upload-btn");
  uploadBtn.disabled = true;
  setStatus(`<span class="spinner"></span>Uploading ${documents.length} document${documents.length === 1 ? "" : "s"}…`);

  const headers = { "Content-Type": "application/json" };
  if (apiKey) headers["X-API-Key"] = apiKey;

  let resp, body;
  try {
    resp = await fetch(`${window.AUDIT_API_BASE}/intake`, {
      method: "POST",
      headers,
      body: JSON.stringify({ engagement, documents }),
    });
    body = await resp.json();
  } catch (err) {
    setStatus(`Network error: ${esc(String(err))}`, "error");
    uploadBtn.disabled = false;
    return;
  }

  if (!resp.ok) {
    const detail = Array.isArray(body.detail)
      ? body.detail.map((d) => d.msg).join(" · ")
      : body.detail || `HTTP ${resp.status}`;
    setStatus(`Upload failed: ${esc(detail)}`, "error");
    uploadBtn.disabled = false;
    return;
  }

  setStatus("", "success");
  uploadBtn.disabled = false;
  showResult(body, documents, engagement);
}

// ── Result panel ─────────────────────────────────────────────────────────────

function showResult(body, documents, engagement) {
  const panel = document.getElementById("result-panel");

  document.getElementById("result-intake-id").textContent = body.intake_id;

  // Per-doc IDs with their titles
  const idsEl = document.getElementById("result-doc-ids");
  idsEl.innerHTML = "";
  body.document_ids.forEach((id, i) => {
    const row = document.createElement("div");
    row.className = "doc-id-row";
    row.innerHTML = `
      <span class="doc-id-label">${esc(documents[i]?.title || `Doc ${i + 1}`)}</span>
      <span class="doc-id-value">${esc(id)}</span>
    `;
    idsEl.appendChild(row);
  });

  // CLI command
  const ids   = body.document_ids.join(" \\\n    ");
  const cmd   = `audit-orchestrator run \\\n  --intake-id ${ids} \\\n  --engagement ${engagement} \\\n  --markdown out/workpaper.md`;
  document.getElementById("cli-cmd").textContent = cmd;

  panel.classList.remove("hidden");
  panel.scrollIntoView({ behavior: "smooth", block: "start" });

  // Copy button
  document.getElementById("copy-btn").addEventListener("click", async () => {
    await navigator.clipboard.writeText(cmd).catch(() => {});
    const btn = document.getElementById("copy-btn");
    btn.classList.add("copied");
    btn.innerHTML = `<svg viewBox="0 0 16 16" fill="currentColor" width="14" height="14"><path d="M13.78 4.22a.75.75 0 0 1 0 1.06l-7.25 7.25a.75.75 0 0 1-1.06 0L2.22 9.28a.75.75 0 0 1 1.06-1.06L6 10.94l6.72-6.72a.75.75 0 0 1 1.06 0z"/></svg> Copied!`;
    setTimeout(() => {
      btn.classList.remove("copied");
      btn.innerHTML = `<svg viewBox="0 0 16 16" fill="currentColor" width="14" height="14"><path d="M4 2a2 2 0 0 1 2-2h6a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V2zm2-1a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1V2a1 1 0 0 0-1-1H6z"/><path d="M2 5a1 1 0 0 0-1 1v8a1 1 0 0 0 1 1h7a1 1 0 0 0 1-1v-1H2V6a1 1 0 0 0-1-1z"/></svg> Copy`;
    }, 2000);
  });

  // "Start live assessment" — POST /api/runs then redirect to index.html
  document.getElementById("go-live-btn").addEventListener("click", async () => {
    const btn = document.getElementById("go-live-btn");
    btn.disabled = true;
    btn.textContent = "Starting…";
    try {
      const r = await fetch(`${window.AUDIT_API_BASE}/api/runs`, { method: "POST" });
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        const msg = d.detail || `HTTP ${r.status}`;
        document.getElementById("go-live-hint").textContent =
          `Could not start run: ${msg}`;
        btn.disabled = false;
        btn.textContent = "Start live assessment →";
        return;
      }
      // Redirect to live viewer
      window.location.href = "index.html";
    } catch (err) {
      document.getElementById("go-live-hint").textContent =
        `Network error: ${String(err)}`;
      btn.disabled = false;
      btn.textContent = "Start live assessment →";
    }
  });

  // "Upload more" — reset form
  document.getElementById("upload-more-btn").addEventListener("click", () => {
    panel.classList.add("hidden");
    document.getElementById("doc-list").innerHTML = "";
    docCount = 0;
    addSlot();
    document.getElementById("engagement-input").focus();
    window.scrollTo({ top: 0, behavior: "smooth" });
  });
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function esc(s) {
  const d = document.createElement("div");
  d.textContent = String(s);
  return d.innerHTML;
}

// ── Init ──────────────────────────────────────────────────────────────────────

function addSlot() {
  document.getElementById("doc-list").appendChild(makeDocSlot());
}

// Inline engagement error span (added dynamically so HTML stays clean)
function initEngagementError() {
  const input = document.getElementById("engagement-input");
  const err   = document.createElement("div");
  err.className = "inline-error";
  err.id = "err-engagement";
  input.after(err);
  input.addEventListener("input", () => {
    if (input.value.trim()) {
      input.classList.remove("invalid");
      err.classList.remove("visible");
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  initEngagementError();
  addSlot(); // start with one empty slot
  document.getElementById("add-doc").addEventListener("click", addSlot);
  document.getElementById("upload-btn").addEventListener("click", upload);
});
