# Quickstart Guide

> **Get up and running with Audit Orchestrator in under 2 minutes.**

---

## 🚀 Installation & Environment Setup

```bash
# 1. Clone repository & create virtual environment
git clone https://github.com/anjeshdubey/Audit-Agent-Orchestrator.git
cd Audit-Agent-Orchestrator
python -m venv .venv && source .venv/bin/activate

# 2. Install dependencies with preferred provider (or all)
pip install -e '.[anthropic,server,docs]'

# 3. Configure environment keys
cp .env.example .env
# Edit .env and paste your API key (ANTHROPIC_API_KEY, GROQ_API_KEY, etc.)
```

---

## 💻 Usage Options

=== "1. CLI Execution"

    Run a complete audit program against policy documents and emit Markdown + JSON workpapers:

    ```bash
    # Run against default Northwind sample engagement
    audit-orchestrator run --markdown out/workpaper.md
    ```

    ```bash
    # Replay specific intake document IDs
    audit-orchestrator run \
      --intake-id <uuid1> <uuid2> \
      --engagement acme-2026 \
      --markdown out/workpaper.md
    ```

=== "2. Live Demo Server"

    Launch the FastAPI live server for real-time SSE streaming and Human-in-the-Loop review:

    ```bash
    audit-orchestrator serve
    ```

    Open your browser at `http://localhost:8000` and click **Start engagement**.

=== "3. Document Upload UI"

    Upload policy text or drag-and-drop `.txt` / `.md` files via the browser UI:

    1. Launch server: `audit-orchestrator serve`
    2. Open `http://localhost:8000/upload.html`
    3. Fill engagement name, add/drop files, and click **Upload documents**.

=== "4. Serve Engineering Docs"

    Preview these engineering documentation pages locally with hot reloading:

    ```bash
    mkdocs serve
    ```

    Open `http://127.0.0.1:8000` to view the documentation site.

---

## 🧪 Running Tests

Run the full pytest suite to verify deterministic scoring and intake validation:

```bash
python -m pytest tests/ -v
```

---

## 📌 Related Links

* Read the **[System Architecture](architecture/system-design.md)** overview.
* Learn about the **[3-Step Pipeline](architecture/pipeline.md)**.
