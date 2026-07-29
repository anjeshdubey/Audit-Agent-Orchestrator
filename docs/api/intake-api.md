# Intake API & Data Specifications

> **API specification for document ingestion, validation, markup sanitization, and local upload storage.**

---

## 📥 Ingestion Pipeline Overview

The **Intake API** (`POST /intake`) allows clients to submit raw policy documents over HTTP. Every document is validated, stripped of dangerous or noisy HTML/XML markup, and stored as an opaque JSON artifact:

```mermaid
flowchart LR
    Client["HTTP Client / Upload UI"] -->|POST /intake| AuthCheck{"API Key Valid?"}
    AuthCheck -->|No| R401["401 Unauthorized"]
    AuthCheck -->|Yes| Pydantic["Pydantic Validation<br/>(Size <= 1MB, Required Fields)"]
    Pydantic -->|Invalid| R422["422 Validation Error"]
    Pydantic -->|Valid| Strip["HTML/XML Markup Stripper"]
    Strip --> Persist["Persist to data/uploads/<uuid>.json"]
    Persist --> Resp["200 OK<br/>(intake_id, document_ids)"]

    style Client fill:#1e293b,stroke:#475569,color:#fff
    style AuthCheck fill:#0f172a,stroke:#334155,color:#fff
    style Strip fill:#064e3b,stroke:#047857,color:#fff
    style Persist fill:#1e1b4b,stroke:#4338ca,color:#fff
```

---

## 📋 API Endpoints Summary

| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `POST` | `/intake` | Ingest and store policy documents | Optional (`X-API-Key` if configured) |
| `POST` | `/api/runs` | Initialize compliance engagement run | None |
| `GET` | `/api/runs/{id}/events` | SSE Stream for live execution logs | None |
| `POST` | `/api/runs/{id}/controls/{cid}/decision` | Submit Human-in-the-Loop decision | None |
| `GET` | `/api/runs/{id}/workpaper` | Fetch final generated Workpaper JSON | None |

---

## 📄 `POST /intake` Specification

### Request Body Schema (`IntakeRequest`)

```json
{
  "engagement": "acme-corp-soc2-2026",
  "documents": [
    {
      "title": "Access Control Policy",
      "text": "<p>All employees must use <b>multi-factor authentication</b> when accessing production systems.</p>",
      "source_url": "https://internal.acme.com/policies/access-control"
    }
  ]
}
```

```mermaid
classDiagram
    class IntakeRequest {
        +string engagement
        +List~DocumentUpload~ documents
    }

    class DocumentUpload {
        +Optional~string~ id
        +string title
        +string text
        +Optional~string~ source_url
    }

    class StoredDocument {
        +string id
        +string title
        +string text
        +Optional~string~ source_url
        +datetime uploaded_at
    }

    IntakeRequest "1" -- "*" DocumentUpload : contains
    DocumentUpload ..> StoredDocument : sanitized & converted to
```

---

## 🧹 Document Sanitization & Size Constraints

```mermaid
graph TD
    Raw["Raw Input Text"] --> SizeCheck{"UTF-8 Byte Length <= 1,048,576?"}
    SizeCheck -->|Exceeds 1MB| ErrSize["Raise 422: Document text exceeds limit"]
    SizeCheck -->|Passes| StripTags["Regex Regex Tag Stripper: <[^>]+>"]
    StripTags --> TrimTitle["Trim whitespace on Title & Text"]
    TrimTitle --> CleanDoc["Stored Document Object"]

    style CleanDoc fill:#16a34a,stroke:#15803d,color:#fff
    style ErrSize fill:#dc2626,stroke:#b91c1c,color:#fff
```

---

## 📂 Upload Storage & Retention Lifecycle

* **Storage Path**: Documents are saved under `data/uploads/<doc_id>.json`.
* **Git Isolation**: `data/uploads/` is ignored by Git (except `.gitkeep`).
* **30-Day Cleanup**: `cleanup_old_uploads()` automatically purges uploaded documents older than 30 days based on their `uploaded_at` timestamp.

---

## 📌 Next Steps

* Learn about **[SSE Event Streaming & Workpaper Schemas](events-sse.md)**.
* Read the **[Verification Engine Deep Dive](../operations/verification-engine.md)**.
