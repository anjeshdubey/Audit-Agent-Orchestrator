"""Tests for Phase 3 intake: validator, ingestor, router, CLI --intake-id.

All tests are self-contained — no network calls, no real filesystem side
effects outside a temporary directory provided by pytest's tmp_path fixture.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Validator tests
# ---------------------------------------------------------------------------


from audit_orchestrator.intake.validator import (
    DocumentUpload,
    IntakeRequest,
    MAX_DOCUMENT_BYTES,
    StoredDocument,
    _strip_markup,
    validate_and_sanitise,
)


class TestStripMarkup:
    def test_removes_html_tags(self):
        assert _strip_markup("<b>Hello</b> <em>world</em>") == "Hello world"

    def test_removes_nested_tags(self):
        assert _strip_markup("<div><p>Text</p></div>") == "Text"

    def test_plain_text_unchanged(self):
        assert _strip_markup("plain text with no tags") == "plain text with no tags"

    def test_empty_string(self):
        assert _strip_markup("") == ""


class TestDocumentUpload:
    def test_valid_document(self):
        doc = DocumentUpload(title="Policy A", text="All employees must use MFA.")
        assert doc.title == "Policy A"
        assert doc.text == "All employees must use MFA."

    def test_missing_title_raises(self):
        with pytest.raises(Exception):
            DocumentUpload(title="", text="Some text")

    def test_missing_text_raises(self):
        with pytest.raises(Exception):
            DocumentUpload(title="Policy A", text="")

    def test_text_over_size_limit_raises(self):
        big = "x" * (MAX_DOCUMENT_BYTES + 1)
        with pytest.raises(Exception, match="limit"):
            DocumentUpload(title="Big doc", text=big)

    def test_text_at_exact_limit_ok(self):
        # Exactly at the limit (ASCII so byte count == char count)
        at_limit = "x" * MAX_DOCUMENT_BYTES
        doc = DocumentUpload(title="Big doc", text=at_limit)
        assert len(doc.text) == MAX_DOCUMENT_BYTES

    def test_optional_id_and_source_url(self):
        doc = DocumentUpload(
            id="my-id",
            title="P",
            text="t",
            source_url="https://example.com/policy",
        )
        assert doc.id == "my-id"
        assert doc.source_url == "https://example.com/policy"


class TestIntakeRequest:
    def test_valid_request(self):
        req = IntakeRequest(
            engagement="acme-2026",
            documents=[
                DocumentUpload(title="Policy A", text="Text A"),
                DocumentUpload(title="Policy B", text="Text B"),
            ],
        )
        assert req.engagement == "acme-2026"
        assert len(req.documents) == 2

    def test_empty_documents_raises(self):
        with pytest.raises(Exception):
            IntakeRequest(engagement="acme", documents=[])

    def test_duplicate_titles_raises(self):
        with pytest.raises(Exception, match="unique"):
            IntakeRequest(
                engagement="acme",
                documents=[
                    DocumentUpload(title="Same", text="A"),
                    DocumentUpload(title="Same", text="B"),
                ],
            )

    def test_empty_engagement_raises(self):
        with pytest.raises(Exception):
            IntakeRequest(
                engagement="",
                documents=[DocumentUpload(title="P", text="t")],
            )


class TestValidateAndSanitise:
    def test_strips_markup_from_text(self):
        doc = DocumentUpload(title="Policy", text="<p>Hello</p>")
        stored = validate_and_sanitise(doc, "test-id")
        assert stored.text == "Hello"
        assert stored.id == "test-id"

    def test_title_stripped_of_whitespace(self):
        doc = DocumentUpload(title="  Policy  ", text="text")
        stored = validate_and_sanitise(doc, "id")
        assert stored.title == "Policy"

    def test_returns_stored_document(self):
        doc = DocumentUpload(title="P", text="t", source_url="https://example.com")
        stored = validate_and_sanitise(doc, "abc")
        assert isinstance(stored, StoredDocument)
        assert stored.source_url == "https://example.com"


# ---------------------------------------------------------------------------
# Ingestor tests
# ---------------------------------------------------------------------------


from audit_orchestrator.intake.ingestor import (
    RETENTION_DAYS,
    cleanup_old_uploads,
    load_document,
    persist_document,
)


class TestPersistAndLoad:
    def test_round_trip(self, tmp_path):
        """persist_document → load_document returns identical data."""
        from audit_orchestrator.intake.validator import DocumentUpload, validate_and_sanitise

        doc_id = uuid.uuid4().hex
        doc = validate_and_sanitise(
            DocumentUpload(title="Round Trip Policy", text="<b>text</b>"),
            doc_id,
        )

        with patch(
            "audit_orchestrator.intake.ingestor._upload_dir", return_value=tmp_path
        ):
            persist_document(doc)
            stored = load_document(doc_id)

        assert stored.id == doc_id
        assert stored.title == "Round Trip Policy"
        assert stored.text == "text"  # markup stripped by validate_and_sanitise

    def test_load_missing_raises(self, tmp_path):
        with patch(
            "audit_orchestrator.intake.ingestor._upload_dir", return_value=tmp_path
        ):
            with pytest.raises(FileNotFoundError):
                load_document("does-not-exist")


class TestCleanupOldUploads:
    def test_deletes_old_files(self, tmp_path):
        from datetime import datetime, timedelta, timezone

        from audit_orchestrator.intake.validator import DocumentUpload, validate_and_sanitise

        old_id = uuid.uuid4().hex
        old_doc = validate_and_sanitise(DocumentUpload(title="Old", text="old"), old_id)
        old_doc = old_doc.model_copy(
            update={"uploaded_at": datetime.now(timezone.utc) - timedelta(days=31)}
        )
        (tmp_path / f"{old_id}.json").write_text(old_doc.model_dump_json())

        new_id = uuid.uuid4().hex
        new_doc = validate_and_sanitise(DocumentUpload(title="New", text="new"), new_id)
        (tmp_path / f"{new_id}.json").write_text(new_doc.model_dump_json())

        with patch(
            "audit_orchestrator.intake.ingestor._upload_dir", return_value=tmp_path
        ):
            deleted = cleanup_old_uploads(retention_days=30)

        assert len(deleted) == 1
        assert not (tmp_path / f"{old_id}.json").exists()
        assert (tmp_path / f"{new_id}.json").exists()

    def test_skips_corrupt_files(self, tmp_path):
        (tmp_path / "corrupt.json").write_text("not valid json {{{")
        with patch(
            "audit_orchestrator.intake.ingestor._upload_dir", return_value=tmp_path
        ):
            deleted = cleanup_old_uploads()
        assert deleted == []


# ---------------------------------------------------------------------------
# Router / FastAPI tests
# ---------------------------------------------------------------------------


from audit_orchestrator.server import app


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def intake_client(tmp_path):
    """TestClient with the upload dir patched to a temp directory."""
    with patch(
        "audit_orchestrator.intake.ingestor._upload_dir", return_value=tmp_path
    ):
        yield TestClient(app), tmp_path


class TestIntakeEndpoint:
    def test_valid_intake_stores_documents(self, intake_client):
        client, tmp_path = intake_client
        payload = {
            "engagement": "test-eng",
            "documents": [
                {"title": "Policy A", "text": "All employees must use MFA."},
                {"title": "Policy B", "text": "Data must be encrypted at rest."},
            ],
        }
        resp = client.post("/intake", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert "intake_id" in body
        assert len(body["document_ids"]) == 2
        assert "stored_paths" not in body  # server-side paths are not exposed
        assert len(list(tmp_path.glob("*.json"))) == 2

    def test_markup_stripped_in_stored_doc(self, intake_client):
        client, tmp_path = intake_client
        payload = {
            "engagement": "test-eng",
            "documents": [{"title": "HTML Policy", "text": "<p>Secure the data.</p>"}],
        }
        resp = client.post("/intake", json=payload)
        assert resp.status_code == 200
        doc_id = resp.json()["document_ids"][0]
        stored_json = json.loads((tmp_path / f"{doc_id}.json").read_text())
        assert "<p>" not in stored_json["text"]
        assert "Secure the data." in stored_json["text"]

    def test_duplicate_titles_returns_422(self, intake_client):
        client, _ = intake_client
        payload = {
            "engagement": "test-eng",
            "documents": [
                {"title": "Same", "text": "A"},
                {"title": "Same", "text": "B"},
            ],
        }
        resp = client.post("/intake", json=payload)
        assert resp.status_code == 422

    def test_empty_documents_returns_422(self, intake_client):
        client, _ = intake_client
        resp = client.post("/intake", json={"engagement": "x", "documents": []})
        assert resp.status_code == 422

    def test_missing_title_returns_422(self, intake_client):
        client, _ = intake_client
        payload = {"engagement": "x", "documents": [{"text": "Some text"}]}
        resp = client.post("/intake", json=payload)
        assert resp.status_code == 422

    def test_api_key_auth_rejected_when_key_set(self, intake_client, monkeypatch):
        client, _ = intake_client
        monkeypatch.setenv("INTAKE_API_KEY", "secret123")
        payload = {
            "engagement": "x",
            "documents": [{"title": "P", "text": "t"}],
        }
        resp = client.post("/intake", json=payload)
        assert resp.status_code == 401

    def test_api_key_auth_accepted_with_correct_key(self, intake_client, monkeypatch):
        client, _ = intake_client
        monkeypatch.setenv("INTAKE_API_KEY", "secret123")
        payload = {
            "engagement": "x",
            "documents": [{"title": "P", "text": "t"}],
        }
        resp = client.post("/intake", json=payload, headers={"X-API-Key": "secret123"})
        assert resp.status_code == 200

    def test_caller_supplied_id_preserved(self, intake_client):
        client, tmp_path = intake_client
        payload = {
            "engagement": "x",
            "documents": [{"id": "my-custom-id", "title": "P", "text": "t"}],
        }
        resp = client.post("/intake", json=payload)
        assert resp.status_code == 200
        assert resp.json()["document_ids"] == ["my-custom-id"]
        assert (tmp_path / "my-custom-id.json").exists()


# ---------------------------------------------------------------------------
# CLI --intake-id tests (task 3.7)
# ---------------------------------------------------------------------------


from audit_orchestrator.cli import main
from audit_orchestrator.intake.validator import DocumentUpload, validate_and_sanitise


class TestCLIIntakeId:
    def test_missing_intake_id_exits_1(self, tmp_path, capsys):
        """Requesting a non-existent intake ID should exit with code 1."""
        result = main(
            [
                "run",
                "--intake-id", "does-not-exist",
                "--out", str(tmp_path / "wp.json"),
            ]
        )
        assert result == 1
        captured = capsys.readouterr()
        assert "not found" in captured.err.lower()

    def test_intake_id_loads_documents(self, tmp_path):
        """A valid intake ID produces the same doc dict as a direct load."""
        doc_id = uuid.uuid4().hex
        stored = validate_and_sanitise(
            DocumentUpload(title="Intake Policy", text="MFA required."), doc_id
        )

        with patch(
            "audit_orchestrator.intake.ingestor._upload_dir", return_value=tmp_path
        ):
            from audit_orchestrator.intake.ingestor import persist_document
            persist_document(stored)

            from audit_orchestrator.program import load_evidence_from_intake_ids
            with patch(
                "audit_orchestrator.intake.ingestor._upload_dir", return_value=tmp_path
            ):
                docs = load_evidence_from_intake_ids([doc_id])

        assert "Intake Policy" in docs
        assert docs["Intake Policy"] == "MFA required."


# ---------------------------------------------------------------------------
# program.py helpers (task 3.6)
# ---------------------------------------------------------------------------


class TestLoadEvidenceFromPaths:
    def test_loads_json_intake_document(self, tmp_path):
        from audit_orchestrator.program import load_evidence_from_paths

        doc_id = uuid.uuid4().hex
        stored = validate_and_sanitise(
            DocumentUpload(title="JSON Policy", text="<em>Secure</em> data."), doc_id
        )
        path = tmp_path / f"{doc_id}.json"
        path.write_text(stored.model_dump_json())

        docs = load_evidence_from_paths([path])
        assert "JSON Policy" in docs
        assert "<em>" not in docs["JSON Policy"]  # markup already stripped on intake

    def test_loads_plain_text_file(self, tmp_path):
        from audit_orchestrator.program import load_evidence_from_paths

        p = tmp_path / "policy.txt"
        p.write_text("Plain text content.")
        docs = load_evidence_from_paths([p])
        assert docs["policy.txt"] == "Plain text content."

    def test_missing_file_raises(self, tmp_path):
        from audit_orchestrator.program import load_evidence_from_paths

        with pytest.raises(FileNotFoundError):
            load_evidence_from_paths([tmp_path / "nonexistent.json"])

    def test_json_without_text_key_raises(self, tmp_path):
        from audit_orchestrator.program import load_evidence_from_paths

        p = tmp_path / "bad.json"
        p.write_text(json.dumps({"not_text": "value"}))
        with pytest.raises(ValueError, match="missing 'text' key"):
            load_evidence_from_paths([p])


class TestLoadEvidenceFromIntakeIds:
    def test_empty_list_raises(self):
        """An empty ID list should raise immediately, not return an empty dict."""
        from audit_orchestrator.program import load_evidence_from_intake_ids

        with pytest.raises(ValueError, match="At least one"):
            load_evidence_from_intake_ids([])

    def test_unknown_id_raises_file_not_found(self, tmp_path):
        from audit_orchestrator.program import load_evidence_from_intake_ids

        with patch(
            "audit_orchestrator.intake.ingestor._upload_dir", return_value=tmp_path
        ):
            with pytest.raises(FileNotFoundError):
                load_evidence_from_intake_ids(["nonexistent-id"])
