# State Machine & Human-in-the-Loop (HITL)

> **Architectural breakdown of the LangGraph state machine, checkpointing, and human review routing.**

---

## 🔄 LangGraph State Machine Workflow

The execution loop for evaluating engagement controls is built as a stateful graph using **LangGraph**:

```mermaid
stateDiagram-v2
    [*] --> InitializeRun : POST /api/runs
    
    state AssessmentLoop {
        [*] --> SelectControl
        SelectControl --> ExtractEvidence : Run 3-Step Pipeline
        ExtractEvidence --> ScoreControl
        
        state DecisionGate <<choice>>
        ScoreControl --> DecisionGate
        
        DecisionGate --> AutoFinalize : Clean & High Confidence (documented)
        DecisionGate --> TriggerInterrupt : Partial / Low Conf / Errored
        
        state HumanReview {
            TriggerInterrupt --> PendingReview : interrupt() saved to MemorySaver
            PendingReview --> SubmitDecision : POST /decision (approve/reject)
            SubmitDecision --> FinalizeWithOverride
        }
        
        AutoFinalize --> CheckNextControl
        FinalizeWithOverride --> CheckNextControl
        
        state CheckNextControl <<choice>>
        CheckNextControl --> SelectControl : More controls remaining
        CheckNextControl --> BuildWorkpaper : All controls processed
    }

    BuildWorkpaper --> RunComplete
    RunComplete --> [*]
```

---

## 🧠 LangGraph State Schema (`EngagementState`)

The state object passed between nodes contains the following attributes:

```mermaid
classDiagram
    class EngagementState {
        +string run_id
        +string engagement
        +List~Control~ controls
        +Dict~string, string~ documents
        +int current_index
        +List~ControlAssessment~ assessments
        +Dict~string, ReviewDecision~ review_decisions
        +Workpaper final_workpaper
    }

    class ControlAssessment {
        +string control_id
        +string verdict
        +float confidence
        +List~CitedEvidence~ evidence
        +int rejected_citations
        +string error
    }

    class ReviewDecision {
        +string action
        +string note
        +string timestamp
    }

    EngagementState "1" -- "*" ControlAssessment : contains
    EngagementState "1" -- "*" ReviewDecision : contains
```

---

## ⏸️ Interrupt & Resume Mechanics

Audit Orchestrator uses LangGraph's native `interrupt()` feature to suspend graph execution when human intervention is required:

```mermaid
sequenceDiagram
    autonumber
    participant Node as Assessment Node
    participant LG as LangGraph Runtime
    participant Mem as MemorySaver Checkpointer
    participant API as FastAPI Router
    participant User as Human Reviewer

    Node->>Node: Evaluate Control Verdict
    alt Verdict requires human review
        Node->>LG: Call interrupt(payload)
        LG->>Mem: Save State Snapshot & Thread Config
        LG-->>API: Yield control back to ASGI event loop
        API-->>User: Stream SSE "review_pending" event
        
        Note over User, API: Graph is paused. Server can handle other requests.
        
        User->>API: POST /api/runs/{id}/controls/{cid}/decision
        API->>LG: Resume Graph with Command(resume=decision)
        Mem->>LG: Restore Thread State Snapshot
        LG->>Node: Return decision payload to Node
        Node->>Node: Apply Reviewer Override
    end
```

---

## 📌 Next Steps

* Inspect the **[Intake API Specifications](../api/intake-api.md)**.
* Learn about **[Deployment & Cloud Topology](../operations/deployment.md)**.
