"""Loading the program (control list) and evidence documents."""

from __future__ import annotations

from pathlib import Path

import yaml

from .models import Control

EVIDENCE_SUFFIXES = {".md", ".txt"}


def load_program(path: str | Path) -> list[Control]:
    """Load and validate a control list from a YAML file."""
    raw = yaml.safe_load(Path(path).read_text())
    if not isinstance(raw, list):
        raise ValueError(f"Program file {path} must be a YAML list of controls.")
    return [Control.model_validate(item) for item in raw]


def load_evidence(directory: str | Path) -> dict[str, str]:
    """Load every evidence document in a directory, keyed by filename.

    MVP-scale and deliberately retrieval-free: documents are small enough to
    pass whole into context, which also avoids chunking splitting a passage we
    need to cite.
    """
    directory = Path(directory)
    docs: dict[str, str] = {}
    for file in sorted(directory.iterdir()):
        if file.is_file() and file.suffix.lower() in EVIDENCE_SUFFIXES:
            docs[file.name] = file.read_text()
    if not docs:
        raise ValueError(f"No evidence documents found in {directory}.")
    return docs


def load_evidence_from_paths(paths: list[str | Path]) -> dict[str, str]:
    """Load evidence documents from an explicit list of file paths.

    Keys are the bare filenames (same convention as :func:`load_evidence`).
    Accepts the JSON files written by the Phase 3 intake ingestor — those are
    :class:`~audit_orchestrator.intake.validator.StoredDocument` objects whose
    ``text`` field is used directly so that the engine sees clean, markup-free
    text without touching the filesystem a second time.

    Falls back to reading raw text from ``.md`` / ``.txt`` files if the path
    doesn't end in ``.json``.
    """
    import json

    docs: dict[str, str] = {}
    for p in paths:
        p = Path(p)
        if not p.exists():
            raise FileNotFoundError(f"Evidence file not found: {p}")
        if p.suffix.lower() == ".json":
            payload = json.loads(p.read_text(encoding="utf-8"))
            # StoredDocument has a 'text' field; fall back to the raw string if
            # the JSON is not a stored document (e.g. a plain workpaper export).
            text = payload.get("text") if isinstance(payload, dict) else None
            if text is None:
                raise ValueError(
                    f"{p} is not a stored intake document (missing 'text' key)."
                )
            title = payload.get("title", p.stem)
            docs[title] = text
        else:
            docs[p.name] = p.read_text()
    if not docs:
        raise ValueError("No evidence documents found in the provided paths.")
    return docs


def load_evidence_from_intake_ids(intake_ids: list[str]) -> dict[str, str]:
    """Load evidence documents that were previously stored via POST /intake.

    Each *intake_id* is the ``id`` field of a
    :class:`~audit_orchestrator.intake.validator.StoredDocument` written to
    ``data/uploads/<id>.json`` by the ingestor.

    This is the bridge for task 3.6 and for ``audit-orchestrator run
    --intake-id``: it resolves IDs → paths and delegates to
    :func:`load_evidence_from_paths`.
    """
    from .intake.ingestor import load_document

    docs: dict[str, str] = {}
    for doc_id in intake_ids:
        stored = load_document(doc_id)
        docs[stored.title] = stored.text
    if not docs:
        raise ValueError("No intake documents found for the provided IDs.")
    return docs
