"""Intake FastAPI router – POST /intake.

Wires the validator and ingestor into a FastAPI APIRouter so server.py can
mount it with a single ``app.include_router(intake_router)`` call.

Endpoint contract (task 3.3):
  POST /intake
    Body : IntakeRequest  (application/json, API-Key header required)
    200  : IntakeResponse – intake_id, list of stored document IDs
    422  : Pydantic validation errors (automatic FastAPI behaviour)
    401  : Missing / invalid API-Key header

Auth (task 3.1):
  A single shared secret read from the INTAKE_API_KEY environment variable.
  Clients send it as ``X-API-Key: <secret>``.  Absent or wrong key → 401.
  Set INTAKE_API_KEY="" (empty) to disable auth entirely (local dev only).
"""

from __future__ import annotations

import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel

from .ingestor import persist_document
from .validator import IntakeRequest, StoredDocument, validate_and_sanitise

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

_API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


def _require_api_key(key: str | None = Security(_API_KEY_HEADER)) -> str:
    """Dependency: validate the X-API-Key header against INTAKE_API_KEY env var."""
    expected = os.environ.get("INTAKE_API_KEY", "")
    # Auth disabled when env var is empty (local dev).
    if expected == "":
        return ""
    if key != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")
    return key


# ---------------------------------------------------------------------------
# Response model
# ---------------------------------------------------------------------------


class IntakeResponse(BaseModel):
    intake_id: str
    """Unique identifier for this intake batch."""
    document_ids: list[str]
    """IDs of successfully stored documents (in request order).

    Pass these to ``audit-orchestrator run --intake-id`` to replay the
    uploaded documents locally for debugging.
    """


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

intake_router = APIRouter(prefix="/intake", tags=["intake"])


@intake_router.post("", response_model=IntakeResponse, status_code=200)
async def intake_documents(
    body: IntakeRequest,
    _key: str = Depends(_require_api_key),
) -> IntakeResponse:
    """Validate, sanitise, and store uploaded policy documents.

    Each document in the request body is independently validated by the
    Pydantic model, then sanitised (markup stripped) and written to
    ``data/uploads/<uuid>.json``.  Returns a batch ``intake_id`` plus the
    list of stored document IDs so the caller can reference them in a
    subsequent ``POST /api/runs`` (Phase 3 extension).
    """
    intake_id = uuid.uuid4().hex[:12]
    document_ids: list[str] = []

    for doc_upload in body.documents:
        doc_id = doc_upload.id or uuid.uuid4().hex
        stored: StoredDocument = validate_and_sanitise(doc_upload, doc_id)
        persist_document(stored)
        document_ids.append(doc_id)

    return IntakeResponse(
        intake_id=intake_id,
        document_ids=document_ids,
    )
