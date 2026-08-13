"""Engine guarantees: evidence is never invented, findings sort blocker-first."""

from __future__ import annotations

import pytest

from check_engine import (
    BLOCKER,
    FRICTION,
    NOTE,
    EvidenceError,
    Finding,
    RuleError,
    format_findings,
    run_checks,
)

DRAFT = "It seals an image and resolves the seal later.\nEvery run is green.\n"
PROVENANCE = "ProofPrint (did not place)."


def make(**overrides) -> Finding:
    fields = dict(
        rule_id="demo",
        severity=BLOCKER,
        title="Demo",
        evidence="",
        fix="Fix the thing.",
        provenance=PROVENANCE,
    )
    fields.update(overrides)
    return Finding(**fields)


def rule_returning(*findings):
    def rule(text, meta):
        return list(findings)

    return rule


# --------------------------------------------------------------------------
# Finding validation
# --------------------------------------------------------------------------


def test_severity_must_be_known():
    with pytest.raises(RuleError):
        make(severity="critical")


def test_fix_must_be_a_single_sentence():
    with pytest.raises(RuleError):
        make(fix="Move the number up. Then rewrite the opening.")


def test_fix_must_be_imperative():
    with pytest.raises(RuleError):
        make(fix="We should move the number up.")


def test_fix_must_end_in_a_period():
    with pytest.raises(RuleError):
        make(fix="Move the number up")


def test_provenance_is_required():
    with pytest.raises(RuleError):
        make(provenance="   ")


def test_evidence_must_be_trimmed():
    with pytest.raises(RuleError):
        make(evidence="  Every run is green.  ")


def test_evidence_may_not_be_a_whole_section():
    with pytest.raises(RuleError):
        make(evidence="x" * 501)


def test_absence_findings_quote_nothing():
    assert make().is_absence is True
    assert make(evidence="Every run is green.").is_absence is False


# --------------------------------------------------------------------------
# The core guarantee: no invented evidence
# --------------------------------------------------------------------------


def test_invented_evidence_is_rejected():
    liar = rule_returning(make(evidence="The dashboard is always red."))
    with pytest.raises(EvidenceError):
        run_checks(DRAFT, {}, rules=[liar])


def test_paraphrased_evidence_is_rejected():
    paraphraser = rule_returning(make(evidence="Every run is green"))  # dropped the period
    findings = run_checks(DRAFT, {}, rules=[paraphraser])
    assert findings[0].evidence in DRAFT  # a shorter exact span is still exact

    reworded = rule_returning(make(evidence="Every run was green."))
    with pytest.raises(EvidenceError):
        run_checks(DRAFT, {}, rules=[reworded])


def test_wrong_span_offsets_are_rejected():
    misplaced = rule_returning(make(evidence="Every run is green.", span=(0, 19)))
    with pytest.raises(EvidenceError):
        run_checks(DRAFT, {}, rules=[misplaced])


def test_span_is_filled_in_from_the_draft():
    quoter = rule_returning(make(evidence="Every run is green."))
    finding = run_checks(DRAFT, {}, rules=[quoter])[0]
    start, end = finding.span
    assert DRAFT[start:end] == "Every run is green."


def test_absence_findings_get_no_span():
    finding = run_checks(DRAFT, {}, rules=[rule_returning(make(span=(0, 4)))])[0]
    assert finding.span is None


def test_a_rule_may_not_emit_findings_under_another_id():
    def impostor(text, meta):
        return [make(rule_id="somebody-else")]

    impostor.rule_id = "demo"
    with pytest.raises(RuleError):
        run_checks(DRAFT, {}, rules=[impostor])


def test_non_findings_are_rejected():
    with pytest.raises(RuleError):
        run_checks(DRAFT, {}, rules=[lambda text, meta: ["not a finding"]])


# --------------------------------------------------------------------------
# Ordering and reporting
# --------------------------------------------------------------------------


def test_findings_sort_blocker_first_then_by_position():
    late_blocker = make(title="Late blocker", evidence="Every run is green.")
    early_note = make(title="Early note", severity=NOTE, evidence="It seals an image")
    friction = make(title="Middle", severity=FRICTION)
    findings = run_checks(DRAFT, {}, rules=[rule_returning(early_note, friction, late_blocker)])
    assert [f.title for f in findings] == ["Late blocker", "Middle", "Early note"]


def test_positioned_findings_precede_absences_within_a_severity():
    absence = make(title="Absent")
    quoted = make(title="Quoted", evidence="Every run is green.")
    findings = run_checks(DRAFT, {}, rules=[rule_returning(absence, quoted)])
    assert [f.title for f in findings] == ["Quoted", "Absent"]


def test_identical_findings_are_deduped():
    duplicate = make(evidence="Every run is green.")
    findings = run_checks(DRAFT, {}, rules=[rule_returning(duplicate, duplicate)])
    assert len(findings) == 1


def test_run_checks_defaults_to_the_registry():
    findings = run_checks("# Thing\n\nIt seals an image.\n")
    assert {f.rule_id for f in findings} >= {"no-test-count", "required-links-missing"}


def test_format_findings_reports_counts_and_a_clean_pass():
    assert format_findings([]) == "No findings. Submit it."
    report = format_findings(run_checks(DRAFT, {}, rules=[rule_returning(make())]))
    assert "1 blocker" in report
    assert "evidence: (absent)" in report
    assert PROVENANCE in report
