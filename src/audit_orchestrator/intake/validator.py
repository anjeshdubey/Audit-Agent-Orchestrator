"""Intake validator – Pydantic models and schema-level validation.

Schema rules (task 3.4):
  - `id`           : optional; generated as UUID4 by the ingestor if absent.
  - `title`        : required, non-empty.
  - `text`         : required, non-empty raw text of the policy document.
  - `source_url`   : optional URL string.
  - `uploaded_at`  : set server-side; ignored if supplied by the caller.
  - Size ceiling   : MAX_DOCUMENT_BYTES (default 1 MB) applied to `text`.
  - Markup strip   : basic HTML/XML tags stripped from `text` before storage.

Validation errors are returned as structured payloads — see IntakeError.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator

# 1 MB ceiling on raw text per document.
MAX_DOCUMENT_BYTES = 1_048_576  # bytes (UTF-8 encoded)

_TAG_RE = re.compile(r"<[^>]+>")


def _strip_markup(text: str) -> str:
    """Remove HTML/XML tags from *text*."""
    return _TAG_RE.sub("", text)


# ---------------------------------------------------------------------------
# Request model (what the caller POSTs)
# ---------------------------------------------------------------------------


class DocumentUpload(BaseModel):
    """Schema for a single document in a POST /intake request."""

    id: Optional[str] = Field(
        default=None,
        description="Caller-supplied document ID. Generated as UUID4 if absent.",
    )
    title: str = Field(..., min_length=1, description="Human-readable document title.")
    text: str = Field(..., min_length=1, description="Full raw text of the policy document.")
    source_url: Optional[str] = Field(
        default=None, description="Original URL the document was sourced from."
    )

    @field_validator("text")
    @classmethod
    def text_within_size_limit(cls, v: str) -> str:
        if len(v.encode("utf-8")) > MAX_DOCUMENT_BYTES:
            raise ValueError(
                f"Document text exceeds {MAX_DOCUMENT_BYTES // 1024} KB limit."
            )
        return v


class IntakeRequest(BaseModel):
    """Top-level intake request body."""

    engagement: str = Field(
        ..., min_length=1, description="Engagement / client identifier."
    )
    documents: list[DocumentUpload] = Field(
        ..., min_length=1, description="One or more policy documents to assess."
    )

    @model_validator(mode="after")
    def no_duplicate_titles(self) -> "IntakeRequest":
        titles = [d.title for d in self.documents]
        if len(titles) != len(set(titles)):
            raise ValueError("All document titles within a request must be unique.")
        return self


# ---------------------------------------------------------------------------
# Stored model (what gets persisted to data/uploads/)
# ---------------------------------------------------------------------------


class StoredDocument(BaseModel):
    """Validated, sanitised document as written to data/uploads/."""

    id: str
    title: str
    text: str  # markup-stripped
    source_url: Optional[str]
    uploaded_at: datetime


# ---------------------------------------------------------------------------
# Error response
# ---------------------------------------------------------------------------


class IntakeError(BaseModel):
    """Structured validation-error payload returned on 422."""

    field: str
    message: str


# ---------------------------------------------------------------------------
# Validation entry-point
# ---------------------------------------------------------------------------


def validate_and_sanitise(doc: DocumentUpload, doc_id: str) -> StoredDocument:
    """Sanitise *doc* and return a :class:`StoredDocument` ready for storage.

    Strips HTML/XML markup from ``text``.  The Pydantic validators on
    :class:`DocumentUpload` have already run by the time this is called, so
    size and required-field checks are guaranteed to have passed.
    """
    return StoredDocument(
        id=doc_id,
        title=doc.title.strip(),
        text=_strip_markup(doc.text),
        source_url=doc.source_url,
        uploaded_at=datetime.now(timezone.utc),
    )
