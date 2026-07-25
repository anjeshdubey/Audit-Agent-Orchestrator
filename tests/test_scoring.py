"""Tests for the code-derived verdict and confidence."""

from audit_orchestrator.scoring import derive_verdict_and_confidence


def test_full_coverage_verified_is_documented():
    verdict, conf = derive_verdict_and_confidence(verified=True, matched=2, total=2)
    assert verdict == "documented"
    assert conf > 0.9


def test_partial_coverage_verified_is_partial():
    verdict, conf = derive_verdict_and_confidence(verified=True, matched=1, total=2)
    assert verdict == "partially_documented"
    assert 0.5 < conf < 0.9


def test_no_verified_evidence_is_not_found():
    verdict, conf = derive_verdict_and_confidence(verified=False, matched=0, total=2)
    assert verdict == "not_found"


def test_fabrication_cannot_pass_even_with_claimed_coverage():
    # The load-bearing guarantee: if nothing verified, full *claimed* coverage
    # still cannot produce a documented verdict.
    verdict, _ = derive_verdict_and_confidence(verified=False, matched=2, total=2)
    assert verdict == "not_found"
