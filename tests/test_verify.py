"""Tests for the deterministic quote-verification guardrail."""

from audit_orchestrator.models import Citation
from audit_orchestrator.verify import verify_quote

DOCS = {
    "policy.md": (
        "# Policy\n\n"
        "§4.2 All new hires must complete the Security Awareness course "
        "through the LMS within their first 30 days of employment.\n"
    )
}


def _cite(source: str, quote: str) -> Citation:
    return Citation(source=source, anchor="§4.2", exact_quote=quote)


def test_exact_quote_verifies():
    assert verify_quote(
        _cite("policy.md", "complete the Security Awareness course through the LMS"),
        DOCS,
    )


def test_whitespace_and_case_are_tolerated():
    assert verify_quote(
        _cite("policy.md", "COMPLETE the  Security   Awareness course"),
        DOCS,
    )


def test_paraphrase_is_rejected():
    assert not verify_quote(
        _cite("policy.md", "finish security training within one month of joining"),
        DOCS,
    )


def test_quote_from_unknown_document_is_rejected():
    assert not verify_quote(_cite("nonexistent.md", "anything at all here"), DOCS)


def test_empty_quote_is_rejected():
    # An empty string is a substring of everything — it must not verify.
    assert not verify_quote(_cite("policy.md", ""), DOCS)


def test_trivially_short_quote_is_rejected():
    assert not verify_quote(_cite("policy.md", "the"), DOCS)
