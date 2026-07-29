# SSE & Streaming Protocol

> **Specification for Server-Sent Events (SSE) live updates and Workpaper JSON structures.**

---

## 📡 Live Event Stream Architecture

The live viewer streams pipeline progress via **Server-Sent Events (SSE)** from `GET /api/runs/{run_id}/events`:

```mermaid
sequenceDiagram
    autonumber
    participant UI as Browser SSE Client
    participant Server as FastAPI Endpoint
    participant Queue as Async Event Queue

    UI->>Server: GET /api/runs/{id}/events
    Server-->>UI: 200 OK (text/event-stream)
    
    loop Stream Execution Events
        Queue->>Server: Pop event (control_started)
        Server-->>UI: data: {"type": "control_started", ...}
        
        Queue->>Server: Pop event (review_pending)
        Server-->>UI: data: {"type": "review_pending", ...}
        
        Queue->>Server: Pop event (control_completed)
        Server-->>UI: data: {"type": "control_completed", ...}
    end

    Queue->>Server: Pop event (run_complete)
    Server-->>UI: data: {"type": "run_complete", ...}
    Server-->>UI: Close Stream Connection
```

---

## 📊 SSE Event Types & Payloads

```mermaid
graph TD
    Start["control_started"] --> Complete["control_completed (Auto-approved)"]
    Start --> Review["review_pending (HITL Required)"]
    Review --> Finalized["control_finalized (Human Approved/Rejected)"]
    Complete --> Finish["run_complete (Workpaper Ready)"]
    Finalized --> Finish

    style Start fill:#1e293b,stroke:#475569,color:#fff
    style Review fill:#d97706,stroke:#b45309,color:#fff
    style Complete fill:#16a34a,stroke:#15803d,color:#fff
    style Finalized fill:#16a34a,stroke:#15803d,color:#fff
```

### Event Payload Examples

#### 1. `control_started`
```json
{
  "type": "control_started",
  "index": 0,
  "total": 12,
  "control_id": "CC6.1",
  "assessment": { "control_id": "CC6.1", "title": "Logical Access Controls", "verdict": "pending" }
}
```

#### 2. `review_pending` (Triggers Human Review UI)
```json
{
  "type": "review_pending",
  "index": 2,
  "total": 12,
  "control_id": "CC6.3",
  "assessment": {
    "control_id": "CC6.3",
    "verdict": "partially_documented",
    "confidence": 0.6,
    "coverage_matched": 1,
    "coverage_total": 2
  }
}
```

#### 3. `run_complete`
```json
{
  "type": "run_complete",
  "workpaper": {
    "engagement": "northwind-2026",
    "summary": { "documented": 10, "partially_documented": 2, "not_found": 0, "total": 12 }
  }
}
```

---

## 📄 Immutable Workpaper JSON Schema

```mermaid
classDiagram
    class Workpaper {
        +string engagement
        +string generated_at
        +dict summary
        +List~ControlAssessment~ assessments
        +Dict~string, string~ evidence_documents
    }

    class ControlAssessment {
        +string control_id
        +string title
        +string verdict
        +float confidence
        +int coverage_matched
        +int coverage_total
        +string rationale
        +List~CitedEvidence~ evidence
        +int rejected_citations
        +Optional~ReviewerDecision~ reviewer_decision
    }

    Workpaper "1" -- "*" ControlAssessment : contains
```

---

## 📌 Next Steps

* Dive into the **[Verification Engine Deep Dive](../operations/verification-engine.md)**.
* Read about **[Server Deployment](../operations/deployment.md)**.
