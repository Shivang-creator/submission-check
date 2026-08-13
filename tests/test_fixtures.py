#!/usr/bin/env python3
"""The rule pack, tested against one submission that lost and one that won.

fixtures/proofprint.md is a condensed real losing submission; every blocker in
RULES.md is present in it on purpose. fixtures/firstframe.md is a condensed
winner that answers each of those rules. If the engine cannot tell them apart,
it is not worth running on a real draft.

    python -m unittest discover -s tests
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import check_engine  # noqa: E402  the engine under test
import cli  # noqa: E402  used for its normalising of engine output
from rules import checks  # noqa: E402  the rule pack itself

LOSER = os.path.join(ROOT, "fixtures", "proofprint.md")
WINNER = os.path.join(ROOT, "fixtures", "firstframe.md")

REGISTRY_ATTRS = ("CHECKS", "ALL_CHECKS", "RULES", "CHECK_LIST", "REGISTRY")


def rule_pack():
    """Every rule importing rules.checks put into the engine's registry."""
    if callable(getattr(check_engine, "registry", None)):
        return list(check_engine.registry())
    for name in REGISTRY_ATTRS:
        value = getattr(checks, name, None)
        if value:
            return list(value.values()) if isinstance(value, dict) else list(value)
    return []


def report(path):
    return cli.analyse(path)


def text_of(finding):
    """Everything a finding says, lowercased, for evidence matching."""
    return " ".join(
        str(finding.get(key) or "")
        for key in ("rule", "title", "evidence", "fix", "provenance")
    ).lower()


def mentions(findings, *needles):
    """True if any finding mentions every needle."""
    wanted = [n.lower() for n in needles]
    return any(all(n in text_of(f) for n in wanted) for f in findings)


class TestLosingSubmission(unittest.TestCase):
    """proofprint.md should light up."""

    @classmethod
    def setUpClass(cls):
        cls.report = report(LOSER)
        cls.findings = cls.report["findings"]
        cls.blockers = [f for f in cls.findings if f["severity"] == "blocker"]

    def test_many_blockers(self):
        self.assertGreaterEqual(
            len(self.blockers),
            4,
            "proofprint.md breaks most of RULES.md; got blockers: %s"
            % [f["rule"] for f in self.blockers],
        )

    def test_score_is_low(self):
        self.assertLessEqual(self.report["score"], 60)

    def test_opening_with_a_regulation_is_caught(self):
        self.assertTrue(
            mentions(self.findings, "eu ai act") or mentions(self.findings, "article 50"),
            "the draft opens on a regulation, not a person — rule 5",
        )

    def test_missing_test_count_is_caught(self):
        self.assertTrue(
            mentions(self.findings, "test"),
            "the draft never states a test count — rule 1",
        )

    def test_buried_headline_number_is_caught(self):
        self.assertTrue(
            mentions(self.findings, "34x")
            or mentions(self.findings, "0/64")
            or mentions(self.findings, "buried"),
            "34x / 0-of-64-bits is the best number and it is item 3 of a sub-list — rule 2",
        )

    def test_deferred_audience_is_caught(self):
        self.assertTrue(
            mentions(self.findings, "audience")
            or mentions(self.findings, "newsroom")
            or mentions(self.findings, "what's next"),
            "the only named buyer appears in the roadmap — rule 3",
        )

    def test_unfiled_sdk_bugs_are_caught(self):
        self.assertTrue(
            mentions(self.findings, "bug")
            or mentions(self.findings, "challenges")
            or mentions(self.findings, "upstream"),
            "three good SDK bugs are filed as complaints, not as reports — rule 4",
        )


class TestWinningSubmission(unittest.TestCase):
    """firstframe.md should come back nearly silent."""

    @classmethod
    def setUpClass(cls):
        cls.report = report(WINNER)
        cls.findings = cls.report["findings"]
        cls.blockers = [f for f in cls.findings if f["severity"] == "blocker"]

    def test_no_blockers(self):
        self.assertEqual(
            self.blockers,
            [],
            "firstframe.md answers every blocking rule; flagged: %s"
            % [(f["rule"], f["evidence"]) for f in self.blockers],
        )

    def test_near_zero_findings(self):
        self.assertLessEqual(
            len(self.findings),
            2,
            "expected a near-clean draft; got: %s" % [f["rule"] for f in self.findings],
        )

    def test_score_is_high(self):
        self.assertGreaterEqual(self.report["score"], 85)


class TestTheGap(unittest.TestCase):
    """The two fixtures are the calibration: the engine must separate them."""

    def test_winner_scores_far_above_loser(self):
        loser, winner = report(LOSER), report(WINNER)
        self.assertGreaterEqual(winner["score"] - loser["score"], 30)

    def test_engine_is_deterministic(self):
        self.assertEqual(report(LOSER)["findings"], report(LOSER)["findings"])


class TestFindingQuality(unittest.TestCase):
    """A finding a writer cannot act on is noise, whichever draft it came from."""

    @classmethod
    def setUpClass(cls):
        cls.findings = report(LOSER)["findings"] + report(WINNER)["findings"]

    def test_every_finding_is_graded(self):
        for finding in self.findings:
            self.assertIn(finding["severity"], cli.SEVERITIES, finding)

    def test_quoted_evidence_carries_a_line_number(self):
        for finding in self.findings:
            if finding["evidence"]:
                self.assertIsNotNone(
                    finding["line"],
                    "%s quotes the draft but points nowhere" % finding["rule"],
                )

    def test_every_finding_carries_a_fix_and_its_provenance(self):
        for finding in self.findings:
            self.assertTrue(finding["fix"], "no fix for %s" % finding["rule"])
            self.assertTrue(
                finding["provenance"], "no provenance for %s" % finding["rule"]
            )

    def test_quoted_evidence_appears_in_the_draft(self):
        for path in (LOSER, WINNER):
            with open(path, encoding="utf-8") as handle:
                draft = " ".join(handle.read().split())
            for finding in report(path)["findings"]:
                if finding["evidence"]:
                    self.assertIn(
                        finding["evidence"].strip('"'),
                        draft,
                        "%s quoted something the draft does not say" % finding["rule"],
                    )


class TestRulePack(unittest.TestCase):
    """rules.checks is the pack; every finding must trace back into it."""

    def test_pack_is_not_empty(self):
        self.assertTrue(rule_pack(), "rules.checks exposes no checks")

    def test_pack_covers_rules_md(self):
        self.assertGreaterEqual(
            len(rule_pack()), 10, "RULES.md documents ten rules"
        )

    def test_engine_exposes_an_entry_point(self):
        self.assertTrue(
            any(callable(getattr(check_engine, n, None)) for n in cli.ENGINE_ENTRY_POINTS),
            "check_engine exposes none of %s" % (cli.ENGINE_ENTRY_POINTS,),
        )


def flat(path):
    """A fixture as one line, so assertions survive reflowing the markdown."""
    with open(path, encoding="utf-8") as handle:
        return " ".join(handle.read().split())


def section(text, heading):
    """One ``## heading`` section, up to the next heading."""
    body = text.split(heading, 1)[1]
    return body.split("\n## ", 1)[0]


class TestFixtureContent(unittest.TestCase):
    """The fixtures are the test data; these guard them against drift."""

    @classmethod
    def setUpClass(cls):
        with open(LOSER, encoding="utf-8") as handle:
            cls.loser = handle.read()
        with open(WINNER, encoding="utf-8") as handle:
            cls.winner = handle.read()
        cls.flat_loser = flat(LOSER)
        cls.flat_winner = flat(WINNER)

    def test_loser_opens_on_the_regulation(self):
        self.assertIn(
            "On 2 August 2026 EU AI Act Article 50 became applicable", self.flat_loser
        )

    def test_loser_never_states_a_test_count(self):
        import re

        self.assertIsNone(
            re.search(r"\b\d[\d,]*\s+(tests?|assertions?|test cases?)\b", self.loser),
            "the losing fixture must never state a test count",
        )

    def test_loser_buries_its_best_number(self):
        self.assertIn("34x", self.flat_loser)
        self.assertIn("0/64 bits", self.flat_loser)
        depth = self.flat_loser.index("34x") / len(self.flat_loser)
        self.assertGreater(depth, 0.4, "the best number must be buried, not led with")

    def test_loser_defers_its_audience(self):
        self.assertIn("Newsroom-scale archives", self.flat_loser)
        self.assertGreater(
            self.flat_loser.index("Newsroom-scale archives"),
            self.flat_loser.index("## What's next"),
            "the only named buyer must appear in the roadmap and nowhere earlier",
        )

    def test_loser_complains_about_sdk_bugs_without_filing_them(self):
        challenges = section(self.loser, "## Challenges we ran into")
        self.assertEqual(challenges.count("genblaze."), 3, "three named SDK bugs")
        for filed in ("pull request", "filed", "upstream", "reported it"):
            self.assertNotIn(filed, challenges.lower(), "the loser never files them")

    def test_winner_leads_with_the_person_then_the_number(self):
        self.assertIn("she says no", self.flat_winner)
        self.assertIn(
            "9.3 seconds versus 65.7 seconds, measured on job `j_47cdc2`",
            self.flat_winner,
        )

    def test_winner_states_its_test_count(self):
        self.assertIn("358 executable assertions", self.flat_winner)

    def test_winner_removes_the_reason_not_to_try_it(self):
        self.assertIn("No account, no key, no card", self.flat_winner)

    def test_winner_sent_its_bugs_upstream(self):
        self.assertIn("three pull requests and an issue sent upstream", self.flat_winner)


if __name__ == "__main__":
    unittest.main(verbosity=2)
