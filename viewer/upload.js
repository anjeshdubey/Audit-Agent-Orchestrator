// Phase 3 upload UI — document intake form.
//
// Flow:
//   1. User fills in engagement name + one or more documents (paste or drag-drop file).
//   2. "Upload documents" POSTs to POST /intake.
//   3. On success, shows the result panel with:
//      - Batch intake_id
//      - Per-document IDs (with titles)
//      - Ready-to-paste CLI command
//      - "Start live assessment" button (goes to index.html — note: /api/runs
//        always runs the server-side program; the uploaded docs provide context
//        for that run via the CLI --intake-id flag shown in the result panel)

const MAX_BYTES = 1_048_576; // must match server MAX_DOCUMENT_BYTES

// Monotonic counter — never reset so IDs remain unique even after "Upload more".
let docCount = 0;

// ── Document slot management ────────────────────────────────────────────────

function makeDocSlot() {
  docCount++;
  const idx = docCount;
  const slot = document.createElement("div");
  slot.className = "doc-slot";
  slot.dataset.idx = idx;

  slot.innerHTML = `
    <div class="doc-slot-header">
      <span class="doc-number">Doc 1</span>
      <input
        class="text-input doc-title-input"
        type="text"
        placeholder="Document title (e.g. Access Control Policy)"
        autocomplete="off"
        spellcheck="false"
        id="doc-title-${idx}"
      />
      <button class="remove-btn" title="Remove document" aria-label="Remove document">✕</button>
    </div>

    <div class="drop-zone" id="drop-zone-${idx}">
      <textarea
        class="doc-textarea"
        placeholder="Paste policy text here…"
        id="doc-text-${idx}"
        aria-label="Document text"
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
    <div class="inline-error" id="err-title-${idx}"></div>
    <div class="inline-error" id="err-text-${idx}"></div>
  `;

  // Remove button
  slot.querySelector(".remove-btn").addEventListener("click", () => {
    slot.remove();
    renumberSlots();
  });

  // Char counter + has-content toggle
  const textarea = slot.querySelector(".doc-textarea");
  const counter  = slot.querySelector(`#char-count-${idx}`);
  const dropZone = slot.querySelector(`#drop-zone-${idx}`);
  textarea.addEventListener("input", () => {
    updateCharCount(textarea, counter);
    dropZone.classList.toggle("has-content", textarea.value.trim().length > 0);
  });

  // Drag-and-drop — use relatedTarget to avoid flicker on child elements
  dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropZone.classList.add("drag-over");
  });
  dropZone.addEventListener("dragleave", (e) => {
    if (!dropZone.contains(e.relatedTarget)) {
      dropZone.classList.remove("drag-over");
    }
  });
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
    setStatus(`Only .txt and .md files are supported (got "${esc(file.name)}").`, "error");
    return;
  }

  const reader = new FileReader();

  reader.onerror = () => {
    setStatus(`Could not read "${esc(file.name)}" — the file may be unreadable.`, "error");
  };

  reader.onload = (e) => {
    const textarea  = slot.querySelector(`#doc-text-${idx}`);
    const counter   = slot.querySelector(`#char-count-${idx}`);
    const dropZone  = slot.querySelector(`#drop-zone-${idx}`);
    const fileRow   = slot.querySelector(`#file-row-${idx}`);
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

function showFieldError(el, msg) {
  el.textContent = msg;
  el.classList.add("visible");
}
function clearFieldError(el) {
  el.textContent = "";
  el.classList.remove("visible");
}

function validateForm() {
  let valid = true;

  // Engagement
  const engInput = document.getElementById("engagement-input");
  const engErr   = document.getElementById("err-engagement");
  if (!engInput.value.trim()) {
    engInput.classList.add("invalid");
    showFieldError(engErr, "Engagement name is required.");
    valid = false;
  } else {
    engInput.classList.remove("invalid");
    clearFieldError(engErr);
  }

  // Documents
  const slots = document.querySelectorAll(".doc-slot");
  if (!slots.length) {
    setStatus("Add at least one document before uploading.", "error");
    return false;
  }

  const seenTitles = new Set();
  slots.forEach((slot) => {
    const idx      = slot.dataset.idx;
    const titleEl  = slot.querySelector(`#doc-title-${idx}`);
    const textEl   = slot.querySelector(`#doc-text-${idx}`);
    const dropZone = slot.querySelector(`#drop-zone-${idx}`);
    const errTitle = slot.querySelector(`#err-title-${idx}`);
    const errText  = slot.querySelector(`#err-text-${idx}`);

    const title = titleEl.value.trim();
    // Use trimmed text for the required check; raw value for byte count
    const textTrimmed = textEl.value.trim();
    const bytes = new TextEncoder().encode(textEl.value).length;

    // ── Title ──
    if (!title) {
      titleEl.classList.add("invalid");
      showFieldError(errTitle, "Title is required.");
      valid = false;
    } else if (seenTitles.has(title.toLowerCase())) {
      titleEl.classList.add("invalid");
      showFieldError(errTitle, "Duplicate title — each document must have a unique title.");
      valid = false;
    } else {
      titleEl.classList.remove("invalid");
      clearFieldError(errTitle);
      seenTitles.add(title.toLowerCase());
    }

    // ── Text ──
    if (!textTrimmed) {
      dropZone.classList.add("dz-invalid");
      showFieldError(errText, "Document text is required.");
      valid = false;
    } else if (bytes > MAX_BYTES) {
      dropZone.classList.add("dz-invalid");
      showFieldError(errText, `Document exceeds 1 MB limit (${(bytes / MAX_BYTES).toFixed(2)} MB).`);
      valid = false;
    } else {
      dropZone.classList.remove("dz-invalid");
      clearFieldError(errText);
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
      // Send raw value — the server strips markup server-side
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

  setStatus("", "");
  uploadBtn.disabled = false;
  showResult(body, documents, engagement);
}

// ── Result panel ─────────────────────────────────────────────────────────────
// Uses onclick assignment (not addEventListener) so re-displaying the result
// panel after "Upload more → upload again" never stacks duplicate handlers.

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
  const idArgs = body.document_ids.map((id) => `    ${id}`).join(" \\\n");
  const cmd    = `audit-orchestrator run \\\n  --intake-id \\\n${idArgs} \\\n  --engagement ${engagement} \\\n  --markdown out/workpaper.md`;
  document.getElementById("cli-cmd").textContent = cmd;

  panel.classList.remove("hidden");
  panel.scrollIntoView({ behavior: "smooth", block: "start" });

  // ── Copy button (onclick = no duplicate handlers) ──
  document.getElementById("copy-btn").onclick = async () => {
    const btn = document.getElementById("copy-btn");
    let copied = false;

    // Prefer Clipboard API (requires HTTPS / localhost)
    if (navigator.clipboard && window.isSecureContext) {
      try {
        await navigator.clipboard.writeText(cmd);
        copied = true;
      } catch (_) { /* fall through */ }
    }

    // Fallback: execCommand for non-secure contexts (plain HTTP deploys)
    if (!copied) {
      const ta = document.createElement("textarea");
      ta.value = cmd;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      try { copied = document.execCommand("copy"); } catch (_) {}
      document.body.removeChild(ta);
    }

    if (copied) {
      btn.classList.add("copied");
      btn.innerHTML = `<svg viewBox="0 0 16 16" fill="currentColor" width="14" height="14"><path d="M13.78 4.22a.75.75 0 0 1 0 1.06l-7.25 7.25a.75.75 0 0 1-1.06 0L2.22 9.28a.75.75 0 0 1 1.06-1.06L6 10.94l6.72-6.72a.75.75 0 0 1 1.06 0z"/></svg> Copied!`;
      setTimeout(() => {
        btn.classList.remove("copied");
        btn.innerHTML = `<svg viewBox="0 0 16 16" fill="currentColor" width="14" height="14"><path d="M4 2a2 2 0 0 1 2-2h6a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V2zm2-1a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1V2a1 1 0 0 0-1-1H6z"/><path d="M2 5a1 1 0 0 0-1 1v8a1 1 0 0 0 1 1h7a1 1 0 0 0 1-1v-1H2V6a1 1 0 0 0-1-1z"/></svg> Copy`;
      }, 2000);
    } else {
      btn.textContent = "Select and copy manually";
    }
  };

  // ── Go live (onclick = no duplicate handlers) ──
  // Note: POST /api/runs starts the server's configured program. The uploaded
  // document IDs are for use with --intake-id on the CLI (shown above). The
  // live viewer is useful to confirm the server is running correctly.
  document.getElementById("go-live-btn").onclick = async () => {
    const btn  = document.getElementById("go-live-btn");
    const hint = document.getElementById("go-live-hint");
    btn.disabled = true;
    btn.textContent = "Starting…";
    try {
      const r = await fetch(`${window.AUDIT_API_BASE}/api/runs`, { method: "POST" });
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        hint.textContent = `Could not start run: ${d.detail || `HTTP ${r.status}`}`;
        btn.disabled = false;
        btn.textContent = "Go to live viewer →";
        return;
      }
      window.location.href = "index.html";
    } catch (err) {
      hint.textContent = `Network error: ${String(err)}`;
      btn.disabled = false;
      btn.textContent = "Go to live viewer →";
    }
  };

  // ── Upload more (onclick = no duplicate handlers) ──
  document.getElementById("upload-more-btn").onclick = () => {
    panel.classList.add("hidden");
    document.getElementById("doc-list").innerHTML = "";
    // docCount is NOT reset — keeps IDs monotonically unique
    addSlot();
    setStatus("", "");
    document.getElementById("engagement-input").focus();
    window.scrollTo({ top: 0, behavior: "smooth" });
  };
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function esc(s) {
  const d = document.createElement("div");
  d.textContent = String(s);
  return d.innerHTML;
}

// ── Init ──────────────────────────────────────────────────────────────────────

function addSlot() {
  const list = document.getElementById("doc-list");
  const slot = makeDocSlot();
  list.appendChild(slot);
  // Update the "Doc N" label now that we know the real position
  renumberSlots();
}

function initEngagementError() {
  const input = document.getElementById("engagement-input");
  const err   = document.createElement("div");
  err.className = "inline-error";
  err.id = "err-engagement";
  input.after(err);
  input.addEventListener("input", () => {
    if (input.value.trim()) {
      input.classList.remove("invalid");
      clearFieldError(err);
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  initEngagementError();
  addSlot();
  document.getElementById("add-doc").addEventListener("click", addSlot);
  document.getElementById("upload-btn").addEventListener("click", upload);
});
