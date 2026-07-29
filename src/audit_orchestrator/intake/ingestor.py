"""Intake ingestor – persists validated documents to data/uploads/.

Responsibilities (task 3.5):
  - Accept a validated :class:`StoredDocument`.
  - Write it as ``<upload_dir>/<uuid>.json`` so the filename is opaque and
    collision-free.
  - Provide a cleanup helper that removes files older than RETENTION_DAYS.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .validator import StoredDocument

# Default retention: remove files older than 30 days on cleanup.
RETENTION_DAYS = 30


def _upload_dir() -> Path:
    """Return the upload directory, creating it if necessary.

    Resolves to ``<repo_root>/data/uploads/``.  The repo root is the
    grandparent of ``src/`` — i.e. parents[3] from this file's location:

      ingestor.py           → parents[0] = intake/
      intake/               → parents[1] = audit_orchestrator/
      audit_orchestrator/   → parents[2] = src/
      src/                  → parents[3] = repo_root/
    """
    repo_root = Path(__file__).resolve().parents[3]
    upload_dir = repo_root / "data" / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def persist_document(doc: StoredDocument) -> Path:
    """Write *doc* to ``data/uploads/<doc.id>.json`` and return the path."""
    dest = _upload_dir() / f"{doc.id}.json"
    dest.write_text(
        doc.model_dump_json(indent=2),
        encoding="utf-8",
    )
    return dest


def load_document(doc_id: str) -> StoredDocument:
    """Load a previously persisted document by ID.

    Raises :exc:`FileNotFoundError` if the file does not exist.
    """
    path = _upload_dir() / f"{doc_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"No uploaded document with id={doc_id!r}")
    return StoredDocument.model_validate_json(path.read_text(encoding="utf-8"))


def cleanup_old_uploads(retention_days: int = RETENTION_DAYS) -> list[Path]:
    """Delete upload files older than *retention_days* days.

    Returns the list of deleted paths so callers / tests can verify behaviour.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    deleted: list[Path] = []
    for f in _upload_dir().glob("*.json"):
        try:
            doc = StoredDocument.model_validate_json(f.read_text(encoding="utf-8"))
            if doc.uploaded_at < cutoff:
                f.unlink()
                deleted.append(f)
        except Exception:
            # Corrupt / non-document file — skip silently.
            pass
    return deleted
