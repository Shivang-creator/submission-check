"""One firing case and one clean case for every rule in RULES.md.

Every assertion about evidence goes through run_checks(), which is what enforces
that a quote is a verbatim span of the draft.
"""

from __future__ import annotations

import pytest

from check_engine import BLOCKER, FRICTION, NOTE, Finding, registry, run_checks
from rules import checks

# --------------------------------------------------------------------------
# Fixtures: two short drafts, both modelled on the real entries in RULES.md.
# --------------------------------------------------------------------------

WEAK = """# ProofPrint

## Inspiration
EU AI Act Article 50 became applicable this August, and disclosure of synthetic media is now required.

## What it does
ProofPrint seals an image and resolves the seal later.

- The seal survives re-encoding.
  - A sealed PNG cut 34x to a metadata-stripped JPEG still resolved at 0/64 bits.

## How we built it
We probe Object Lock at startup, so the ledger is immutable.
Every run seals perfectly and the dashboard is always green.
We tested the sealing path by hand before the demo.
It works with no API key.

## Challenges we ran into
The Genblaze SDK drops the retention header when a bucket has Object Lock enabled, and we lost four hours to it.

## What's next
Our first customer would be a compliance auditor at a mid-size studio.
"""

STRONG = """# FirstFrame

9.3s vs 65.7s on job j_47cdc2, live right now, check it yourself: https://firstframe.fly.dev
Someone waited four minutes to watch four seconds and say no; we cut that to nine seconds, and it runs with no API key.
Built for indie game studios shipping a trailer a week, and 485 tests cover the whole render path.

## Proof
We issued a real delete against the sealed object and asserted the AccessDenied refusal.
Run 3 is retained in the UI with a TEST FAULT badge because the encoder timed out.
A neurodivergent tester ran the full task list in design review and again in testing.

## Upstream
We filed 3 PRs and one issue against the Genblaze SDK, each with a minimal reproduction and a failing test.

Repo: https://github.com/example/firstframe
Video: https://youtu.be/abc123
"""

HARD_RULE = "Entries must involve a real neurodivergent user in design or testing."

STRONG_META = {
    "links": {"repo": "https://github.com/example/firstframe"},
    "hard_rules": [HARD_RULE],
}


def check(rule, text: str, meta: dict | None = None) -> list[Finding]:
    """Run one rule through the engine, so evidence is validated against the draft."""
    return run_checks(text, meta or {}, rules=[rule])


def only(findings: list[Finding]) -> Finding:
    assert len(findings) == 1, [f.title for f in findings]
    return findings[0]


# --------------------------------------------------------------------------
# 1. No test count stated
# --------------------------------------------------------------------------


def test_no_test_count_quotes_the_uncounted_testing_claim():
    finding = only(check(checks.no_test_count, WEAK))
    assert finding.severity == BLOCKER
    assert finding.evidence == "We tested the sealing path by hand before the demo."
    assert "ProofPrint" in finding.provenance


def test_no_test_count_reports_absence_when_testing_is_never_mentioned():
    finding = only(check(checks.no_test_count, "# Thing\n\nIt seals an image.\n"))
    assert finding.is_absence
    assert finding.evidence == ""


@pytest.mark.parametrize(
    "line",
    [
        "The suite runs 358 executable assertions on every push.",
        "485 tests cover the whole render path.",
        "tests: 122 green on CI.",
    ],
)
def test_no_test_count_is_quiet_when_a_count_is_stated(line):
    assert check(checks.no_test_count, f"# Thing\n\n{line}\n") == []


# --------------------------------------------------------------------------
# 2. Headline number buried
# --------------------------------------------------------------------------


def test_headline_number_buried_in_a_sub_list():
    finding = only(check(checks.headline_number_buried, WEAK))
    assert finding.severity == BLOCKER
    assert "sub-list" in finding.title
    assert finding.evidence == (
        "A sealed PNG cut 34x to a metadata-stripped JPEG still resolved at 0/64 bits."
    )


def test_headline_number_in_the_opening_passes():
    assert check(checks.headline_number_buried, STRONG) == []


def test_headline_number_absent_entirely():
    finding = only(check(checks.headline_number_buried, "# Thing\n\nIt is fast and it is nice.\n"))
    assert finding.is_absence
    assert "No measured result" in finding.title


# --------------------------------------------------------------------------
# 3. Audience deferred to "What's next"
# --------------------------------------------------------------------------


def test_audience_deferred_to_roadmap():
    finding = only(check(checks.audience_deferred, WEAK))
    assert finding.severity == BLOCKER
    assert finding.evidence == (
        "Our first customer would be a compliance auditor at a mid-size studio."
    )
    assert "What's next" in finding.title


def test_audience_named_up_front_passes():
    assert check(checks.audience_deferred, STRONG) == []


def test_audience_never_named():
    finding = only(check(checks.audience_deferred, "# Thing\n\nIt seals an image.\n"))
    assert finding.is_absence


# --------------------------------------------------------------------------
# 4. SDK bugs written as complaints
# --------------------------------------------------------------------------


def test_bugs_as_complaints_quotes_the_challenges_line():
    finding = only(check(checks.bugs_as_complaints, WEAK))
    assert finding.severity == FRICTION
    assert finding.evidence.startswith("The Genblaze SDK drops the retention header")
    assert "PRs" in finding.provenance


def test_bugs_filed_upstream_pass():
    assert check(checks.bugs_as_complaints, STRONG) == []


def test_bug_language_outside_a_challenges_section_is_not_a_complaint():
    draft = "# Thing\n\n## What it does\nIt retries when the SDK crashes.\n"
    assert check(checks.bugs_as_complaints, draft) == []


# --------------------------------------------------------------------------
# 5. Opens with a regulation, not a person
# --------------------------------------------------------------------------


def test_opens_with_regulation():
    finding = only(check(checks.opens_with_abstraction, WEAK))
    assert finding.severity == FRICTION
    assert finding.evidence.startswith("EU AI Act Article 50 became applicable")


def test_opens_with_a_person_passes():
    assert check(checks.opens_with_abstraction, STRONG) == []


def test_regulation_reached_through_a_named_person_passes():
    draft = "# Thing\n\nMaria read that the EU AI Act became applicable and asked us for proof.\n"
    assert check(checks.opens_with_abstraction, draft) == []


# --------------------------------------------------------------------------
# 6. No visible failure
# --------------------------------------------------------------------------


def test_no_visible_failure_quotes_the_perfect_surface():
    finding = only(check(checks.no_visible_failure, WEAK))
    assert finding.severity == FRICTION
    assert finding.evidence == "Every run seals perfectly and the dashboard is always green."


def test_retained_failure_badge_passes():
    assert check(checks.no_visible_failure, STRONG) == []


def test_a_limitations_heading_counts_as_a_visible_failure():
    draft = "# Thing\n\nIt seals an image.\n\n## Limitations\nHEIC files are out of scope.\n"
    assert check(checks.no_visible_failure, draft) == []


# --------------------------------------------------------------------------
# 7. Guarantee asserted, never attacked
# --------------------------------------------------------------------------


def test_guarantee_probed_not_attacked():
    finding = only(check(checks.guarantee_unattacked, WEAK))
    assert finding.severity == FRICTION
    assert finding.evidence == "We probe Object Lock at startup, so the ledger is immutable."
    assert "issued a real delete" in finding.provenance


def test_guarantee_attacked_passes():
    assert check(checks.guarantee_unattacked, STRONG) == []


def test_no_guarantee_claimed_is_not_a_finding():
    assert check(checks.guarantee_unattacked, "# Thing\n\nIt seals an image.\n") == []


# --------------------------------------------------------------------------
# 8. Required links missing
# --------------------------------------------------------------------------


def test_required_links_all_missing():
    findings = check(checks.required_links_missing, WEAK)
    assert [f.title for f in findings] == [
        "Repo link missing",
        "Live URL missing",
        "Demo video link missing",
    ]
    assert all(f.severity == BLOCKER and f.is_absence for f in findings)


def test_links_found_in_the_draft_body_satisfy_the_rule():
    assert check(checks.required_links_missing, STRONG) == []


def test_links_supplied_through_meta_satisfy_the_rule():
    meta = {
        "links": {
            "repo": "https://github.com/example/x",
            "live": "https://x.example.com",
            "video": "https://youtu.be/x",
        }
    }
    assert check(checks.required_links_missing, "# Thing\n", meta) == []


def test_devpost_url_does_not_count_as_a_live_url():
    draft = "# Thing\n\nSee https://devpost.com/software/thing for details.\n"
    titles = [f.title for f in check(checks.required_links_missing, draft)]
    assert "Live URL missing" in titles


def test_required_links_are_configurable():
    findings = check(checks.required_links_missing, "# Thing\n", {"required_links": ["repo"]})
    assert [f.title for f in findings] == ["Repo link missing"]


# --------------------------------------------------------------------------
# 9. Rules not read
# --------------------------------------------------------------------------


def test_hard_rule_unaddressed():
    finding = only(check(checks.hard_rules_unaddressed, WEAK, {"hard_rules": [HARD_RULE]}))
    assert finding.severity == BLOCKER
    assert finding.is_absence
    assert "neurodivergent" in finding.title
    assert "IncludAI" in finding.provenance


def test_hard_rule_addressed_passes():
    assert check(checks.hard_rules_unaddressed, STRONG, {"hard_rules": [HARD_RULE]}) == []


def test_passing_mention_of_the_topic_does_not_address_the_rule():
    draft = "# Thing\n\nWe agree neurodivergent users matter.\n"
    finding = only(check(checks.hard_rules_unaddressed, draft, {"hard_rules": [HARD_RULE]}))
    assert finding.severity == BLOCKER


def test_missing_hard_rules_is_a_note_not_a_blocker():
    finding = only(check(checks.hard_rules_unaddressed, STRONG))
    assert finding.severity == NOTE
    assert finding.is_absence


# --------------------------------------------------------------------------
# 10. "Works with no API key" not said up front
# --------------------------------------------------------------------------


def test_no_api_key_claim_is_buried():
    finding = only(check(checks.no_api_key_not_upfront, WEAK))
    assert finding.severity == FRICTION
    assert finding.evidence == "It works with no API key."


def test_no_api_key_claim_up_front_passes():
    assert check(checks.no_api_key_not_upfront, STRONG) == []


def test_silence_about_api_keys_is_a_note():
    finding = only(check(checks.no_api_key_not_upfront, "# Thing\n\nIt seals an image.\n"))
    assert finding.severity == NOTE
    assert finding.is_absence


# --------------------------------------------------------------------------
# Cross-cutting: the ten rules together
# --------------------------------------------------------------------------

EXPECTED_RULE_IDS = (
    "no-test-count",
    "headline-number-buried",
    "audience-deferred",
    "bugs-as-complaints",
    "opens-with-abstraction",
    "no-visible-failure",
    "guarantee-unattacked",
    "required-links-missing",
    "hard-rules-unaddressed",
    "no-api-key-not-upfront",
)


def test_all_ten_rules_are_registered():
    assert tuple(rule.rule_id for rule in registry()) == EXPECTED_RULE_IDS


def test_weak_draft_trips_every_rule():
    findings = run_checks(WEAK, {"hard_rules": [HARD_RULE]})
    assert set(f.rule_id for f in findings) == set(EXPECTED_RULE_IDS)


def test_strong_draft_is_clean():
    assert run_checks(STRONG, STRONG_META) == []


def test_every_quote_is_a_verbatim_span_of_the_draft():
    for finding in run_checks(WEAK, {"hard_rules": [HARD_RULE]}):
        if finding.is_absence:
            assert finding.span is None
        else:
            start, end = finding.span
            assert WEAK[start:end] == finding.evidence


def test_rules_are_pure_and_do_not_touch_meta():
    meta = {"hard_rules": [HARD_RULE]}
    before = repr(meta)
    first = run_checks(WEAK, meta)
    second = run_checks(WEAK, meta)
    assert first == second
    assert repr(meta) == before


@pytest.mark.parametrize("rule", list(registry()), ids=lambda r: r.rule_id)
def test_every_rule_survives_degenerate_input(rule):
    for draft in ("", "\n\n", "# Title\n", "```\ncode only\n```\n"):
        for finding in run_checks(draft, {}, rules=[rule]):
            assert finding.evidence == "" or draft.find(finding.evidence) >= 0
