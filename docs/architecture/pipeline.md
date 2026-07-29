# The Core 3-Step Engine Pipeline

> **How Audit Orchestrator extracts evidence, verifies citations, and computes compliance scores deterministically.**

---

## ⚡ The 3-Step Pipeline Flow

Unlike traditional RAG systems that trust LLM outputs, Audit Orchestrator processes every control through a strict 3-step deterministic pipeline:

```mermaid
flowchart TD
    subgraph Step1 ["Step 1: Structured Evidence Extraction"]
        Control["Control Requirement<br/>(e.g., CC6.1 MFA Rule)"]
        Docs["Policy Documents"]
        LLM["Instructor LLM Call"]
        Control --> LLM
        Docs --> LLM
        LLM --> RawCitations["Raw Citations List<br/>(source, anchor, exact_quote)"]
    end

    subgraph Step2 ["Step 2: Deterministic Verification"]
        RawCitations --> VerifyEngine{"verify_quote()<br/>Literal Match Check"}
        VerifyEngine -->|Match Found| VerifiedList["Verified Citations"]
        VerifyEngine -->|Quote Not in Source| RejectList["Rejected Citations<br/>(Fabrication Flagged)"]
    end

    subgraph Step3 ["Step 3: Code-Based Scoring & Verdict"]
        VerifiedList --> Scorer["scoring.py"]
        RejectList --> Scorer
        Scorer --> VerdictRule{"Evaluate Coverage & Verification"}
        
        VerdictRule -->|100% Verified Parts| Doc["Verdict: DOCUMENTED<br/>Conf: HIGH"]
        VerdictRule -->|Partial Verified Parts| Part["Verdict: PARTIALLY_DOCUMENTED<br/>Conf: MEDIUM"]
        VerdictRule -->|0 Verified Parts| NF["Verdict: NOT_FOUND<br/>Conf: HIGH / LOW"]
    end

    style Step1 fill:#1e293b,stroke:#475569,color:#fff
    style Step2 fill:#0f172a,stroke:#334155,color:#fff
    style Step3 fill:#1e1b4b,stroke:#4338ca,color:#fff
```

---

## 🔬 Pipeline Step Breakdown

### Step 1: Structured Evidence Extraction

The model receives the **Control Requirements** and **Document Set**. Using Instructor structured output, it returns a schema containing verbatim quotes for each requirement part:

```mermaid
classDiagram
    class RequirementPart {
        +string part_id
        +string text
    }

    class CitedEvidence {
        +string requirement_part
        +Citation citation
    }

    class Citation {
        +string source
        +string anchor
        +string exact_quote
    }

    RequirementPart "1" -- "*" CitedEvidence : evaluates
    CitedEvidence "1" -- "1" Citation : references
```

---

### Step 2: Deterministic Citation Verification

Before any citation is accepted into the audit record, `verify.py` checks that `exact_quote` exists literally within `source`:

```mermaid
graph LR
    Quote["LLM Quote"] --> Norm1["Normalize Whitespace & Case"]
    DocText["Source Document Text"] --> Norm2["Normalize Whitespace & Case"]
    Norm1 & Norm2 --> Match{"Sub-string Index Of?"}
    Match -->|Index >= 0| Valid["✅ Verified (Authentic)"]
    Match -->|Index == -1| Invalid["❌ Rejected (Unverifiable)"]

    style Valid fill:#16a34a,stroke:#15803d,color:#fff
    style Invalid fill:#dc2626,stroke:#b91c1c,color:#fff
```

> **Anti-Fabrication Rule**: Unverifiable quotes are discarded immediately and recorded in `rejected_citations`. They can never contribute to a `documented` verdict.

---

### Step 3: Code-Based Scoring Matrix

The final verdict is derived directly from requirement coverage metrics:

| Requirement Coverage | Verified Evidence Count | Rejections Present? | Final Verdict | Confidence |
| :--- | :--- | :--- | :--- | :--- |
| **All parts met** ($N/N$) | $\ge 1$ verified quote per part | No | `documented` | **1.0** (High) |
| **Partial parts met** ($k/N$) | $\ge 1$ verified quote | No | `partially_documented` | **0.6** (Medium) |
| **No parts met** ($0/N$) | 0 verified quotes | No | `not_found` | **1.0** (High) |
| **Any parts met** | Claims met but quotes failed verification | Yes | `partially_documented` or `not_found` | **0.3** (Low) |

---

## 📌 Next Steps

* See how the pipeline is orchestrated in the **[State Machine & HITL](state-machine.md)** guide.
* Learn about string normalization in **[Deterministic Verification](../operations/verification-engine.md)**.
