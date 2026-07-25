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
