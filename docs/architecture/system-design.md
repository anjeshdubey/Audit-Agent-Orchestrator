# System Architecture & High-Level Design

> **Detailed technical overview of the Audit Orchestrator system architecture, component breakdown, and runtime data flow.**

---

## 🏛️ High-Level Component Topology

Audit Orchestrator decouples the **interactive user interface**, **orchestration runtime**, and **deterministic core logic** into distinct, modular boundaries:

```mermaid
graph TB
    subgraph Frontend ["User Interface Layer"]
        UI_Static["Static Workpaper Viewer<br/>(viewer/workpaper.html)"]
        UI_Live["Live Engagement Viewer<br/>(viewer/index.html)"]
        UI_Upload["Intake Upload UI<br/>(viewer/upload.html)"]
    end

    subgraph API_Layer ["API & Ingestion Boundary"]
        FastAPI["FastAPI App (server.py)"]
        Router_Intake["Intake Router (/intake)"]
        Router_Runs["Runs Router (/api/runs)"]
        Sanitizer["HTML/XML Sanitizer & Validator"]
    end

    subgraph Orchestrator ["Execution Engine (LangGraph)"]
        StateGraph["LangGraph Workflow Graph"]
        Checkpointer["In-Memory MemorySaver"]
        SSEManager["SSE Event Streamer"]
    end

    subgraph Deterministic_Core ["Core Compliance Logic"]
        Extractor["LLM Structured Extractor"]
        Verifier["Exact Quote Verifier (verify.py)"]
        Scorer["Coverage & Score Calculator (scoring.py)"]
    end

    subgraph Storage ["Local Storage / Persistence"]
        UploadStore["data/uploads/*.json"]
        WorkpaperStore["viewer/data/workpaper.json"]
    end

    UI_Upload -->|POST /intake| Router_Intake
    UI_Live -->|POST /api/runs| Router_Runs
    UI_Live <-->|SSE Stream| SSEManager

    Router_Intake --> Sanitizer --> UploadStore
    Router_Runs --> StateGraph

    StateGraph --> Extractor
    Extractor --> Verifier
    Verifier --> Scorer
    Scorer --> Checkpointer
    Checkpointer --> WorkpaperStore

    style Frontend fill:#1e293b,stroke:#475569,color:#fff
    style API_Layer fill:#0f172a,stroke:#334155,color:#fff
    style Orchestrator fill:#1e1b4b,stroke:#4338ca,color:#fff
    style Deterministic_Core fill:#064e3b,stroke:#047857,color:#fff
    style Storage fill:#312e81,stroke:#4338ca,color:#fff
```

---

## 🔄 End-to-End Execution Sequence

The sequence below illustrates the life cycle of a compliance assessment, from document ingestion to human sign-off:

```mermaid
sequenceDiagram
    autonumber
    actor User as Compliance Auditor
    participant UI as Browser UI / CLI
    participant Server as FastAPI Server
    participant Graph as LangGraph Engine
    participant LLM as Provider Gateway
    participant Core as Verification Core

    User->>UI: Upload Policy Docs or Start Engagement
    UI->>Server: POST /intake (or POST /api/runs)
    Server->>Server: Validate, sanitize, & store documents
    Server->>Graph: Initialize Engagement State
    
    loop For Each Control in Program
        Graph->>LLM: Request Structured Evidence Extraction
        LLM-->>Graph: Return Citation (Source, Anchor, Quote)
        Graph->>Core: Verify Citation against Source Text
        Core-->>Graph: Return Verification Status (Match / Rejected)
        Graph->>Core: Calculate Coverage & Verdict Score
        Core-->>Graph: Return Verdict & Confidence
        
        alt Verdict is Partial / Low Confidence / Errored
            Graph->>Server: Trigger LangGraph interrupt()
            Server-->>UI: Push SSE event (review_pending)
            User->>UI: Approve / Reject Verdict
            UI->>Server: POST /api/runs/{id}/controls/{cid}/decision
            Server->>Graph: Resume Graph Execution
        else Clean High-Confidence Verdict
            Graph->>Server: Auto-finalize Control
            Server-->>UI: Push SSE event (control_completed)
        end
    end

    Graph->>Server: Emit Final Workpaper JSON
    Server-->>UI: Push SSE event (run_complete)
```

---

## 🛡️ Architectural Boundaries & Isolation

```mermaid
grid
```

### 1. Zero-Database & Process Isolation
* **Single-Process Global State**: The server operates without an external database (PostgreSQL/Redis). Active runs and events are maintained in process memory.
* **Pinned Concurrency**: Cloud deployments (Modal) enforce `max_containers=1` to guarantee consistent state without distributed synchronization overhead.

### 2. Multi-Provider Gateway Abstraction
* The core relies on an agnostic gateway (`gateway.py`) supporting **Groq**, **Google Gemini**, **Anthropic**, and **Together AI**.
* Standardized `Instructor` schemas enforce structured outputs across all model providers.

---

## 📌 Next Steps

* Deep dive into the **[Core 3-Step Pipeline](pipeline.md)** to see how citations are verified.
* Examine the **[State Machine & HITL](state-machine.md)** graph design.
