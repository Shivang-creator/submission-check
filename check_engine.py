"""The engine: findings, the rule protocol, the registry, and run_checks().

Design constraints, in order of importance:

1. Evidence is never invented. A Finding either quotes an EXACT span of the
   draft or quotes nothing at all (``evidence=""`` for an absence). run_checks()
   enforces this mechanically -- a rule that returns evidence which is not a
   verbatim slice of the draft raises EvidenceError. That check is the whole
   point of this module; everything else is plumbing.
2. Rules are pure functions ``(text, meta) -> list[Finding]``. No I/O, no
   network, no clock, no randomness. Same draft in, same findings out.
3. Findings sort blocker-first, then by position in the draft, so the top of
   the list is the next thing to fix.

Stdlib only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Any, Callable, Mapping, Protocol, Sequence, runtime_checkable

__all__ = [
    "BLOCKER",
    "FRICTION",
    "NOTE",
    "SEVERITIES",
    "EvidenceError",
    "Finding",
    "Rule",
    "RuleError",
    "format_findings",
    "register",
    "registry",
    "run_checks",
]

BLOCKER = "blocker"
FRICTION = "friction"
NOTE = "note"

#: Ordered worst-first; this ordering is what "blocker-first" means.
SEVERITIES: tuple[str, ...] = (BLOCKER, FRICTION, NOTE)
_SEVERITY_RANK = {name: i for i, name in enumerate(SEVERITIES)}

#: Evidence longer than this is a rule quoting lazily, not quoting precisely.
MAX_EVIDENCE = 500


class RuleError(ValueError):
    """A rule is malformed: bad severity, multi-sentence fix, wrong id."""


class EvidenceError(ValueError):
    """A rule produced evidence that is not a verbatim span of the draft."""


_SENTENCE_TAIL = re.compile(r"[.!?]\s+\S")
_FIRST_WORD = re.compile(r"[A-Za-z']+")
# A fix that opens with one of these is describing, not instructing.
_WEAK_OPENERS = frozenset(
    {"we", "i", "you", "it", "this", "that", "there", "the", "a", "an", "our", "my", "they"}
)


def _is_one_imperative_sentence(text: str) -> bool:
    body = text.strip()
    if not body or "\n" in body:
        return False
    if not body.endswith("."):
        return False
    if _SENTENCE_TAIL.search(body):  # a second sentence has started
        return False
    first = _FIRST_WORD.match(body)
    return bool(first) and first.group(0).lower() not in _WEAK_OPENERS


@dataclass(frozen=True)
class Finding:
    """One thing wrong with a draft submission.

    Attributes:
        rule_id: Stable id of the rule that produced this, e.g. ``no-test-count``.
        severity: One of ``blocker`` / ``friction`` / ``note``.
        title: What is wrong, in a few words.
        evidence: An EXACT span copied out of the draft, or ``""`` when the
            problem is that something is absent and there is honestly nothing
            to quote. Never paraphrased, never reconstructed.
        fix: Exactly one imperative sentence.
        provenance: The real hackathon loss this rule came from.
        span: ``(start, end)`` offsets of ``evidence`` in the draft, or None
            for an absence finding. Filled in by run_checks() when omitted.
    """

    rule_id: str
    severity: str
    title: str
    evidence: str
    fix: str
    provenance: str
    span: tuple[int, int] | None = None

    def __post_init__(self) -> None:
        if not self.rule_id.strip():
            raise RuleError("rule_id must not be empty")
        if self.severity not in _SEVERITY_RANK:
            raise RuleError(
                f"{self.rule_id}: severity must be one of {SEVERITIES}, got {self.severity!r}"
            )
        if not self.title.strip():
            raise RuleError(f"{self.rule_id}: title must not be empty")
        if not self.provenance.strip():
            raise RuleError(f"{self.rule_id}: provenance must name the loss the rule came from")
        if not _is_one_imperative_sentence(self.fix):
            raise RuleError(
                f"{self.rule_id}: fix must be one imperative sentence ending in a period, "
                f"got {self.fix!r}"
            )
        if self.evidence != self.evidence.strip():
            raise RuleError(f"{self.rule_id}: evidence must be tightly trimmed, got {self.evidence!r}")
        if len(self.evidence) > MAX_EVIDENCE:
            raise RuleError(
                f"{self.rule_id}: evidence is {len(self.evidence)} chars; quote a span, not a section"
            )

    @property
    def is_absence(self) -> bool:
        """True when the finding is about something missing, so nothing is quoted."""
        return self.evidence == ""

    @property
    def rank(self) -> int:
        return _SEVERITY_RANK[self.severity]

    def render(self) -> str:
        quote = f'\n    evidence: "{self.evidence}"' if self.evidence else "\n    evidence: (absent)"
        return (
            f"[{self.severity.upper()}] {self.title}  ({self.rule_id})"
            f"{quote}"
            f"\n    fix: {self.fix}"
            f"\n    from: {self.provenance}"
        )


@runtime_checkable
class Rule(Protocol):
    """A pure function from a draft to findings.

    Implementations carry a ``rule_id`` attribute (the :func:`register`
    decorator attaches it) so run_checks() can verify that a rule only emits
    findings under its own id.
    """

    rule_id: str

    def __call__(self, text: str, meta: Mapping[str, Any]) -> list[Finding]: ...


_REGISTRY: dict[str, Rule] = {}


def register(rule_id: str) -> Callable[[Callable[..., list[Finding]]], Rule]:
    """Decorator: add a pure ``(text, meta) -> list[Finding]`` function to the registry."""

    def decorate(fn: Callable[..., list[Finding]]) -> Rule:
        if rule_id in _REGISTRY:
            raise RuleError(f"duplicate rule_id {rule_id!r}")
        fn.rule_id = rule_id  # type: ignore[attr-defined]
        _REGISTRY[rule_id] = fn  # type: ignore[assignment]
        return fn  # type: ignore[return-value]

    return decorate


def registry() -> tuple[Rule, ...]:
    """Every registered rule, in registration order."""
    _load_default_rules()
    if not _REGISTRY:
        # Reporting "no findings" because no rules loaded is the worst possible
        # failure mode for this tool, so refuse to do it.
        raise RuleError("no rules registered; import rules.checks before running")
    return tuple(_REGISTRY.values())


def _load_default_rules() -> None:
    # Imported lazily so rules/checks.py can import Finding from here.
    import rules.checks  # noqa: F401


def _validate(finding: object, text: str, rule: Rule) -> Finding:
    if not isinstance(finding, Finding):
        raise RuleError(f"{getattr(rule, 'rule_id', rule)!r} returned {type(finding).__name__}, not Finding")

    declared = getattr(rule, "rule_id", None)
    if declared is not None and finding.rule_id != declared:
        raise RuleError(f"rule {declared!r} emitted a finding under id {finding.rule_id!r}")

    if finding.is_absence:
        return replace(finding, span=None)

    if finding.span is not None:
        start, end = finding.span
        if text[start:end] != finding.evidence:
            raise EvidenceError(
                f"{finding.rule_id}: evidence does not match the draft at {finding.span}: "
                f"{finding.evidence!r}"
            )
        return finding

    start = text.find(finding.evidence)
    if start < 0:
        raise EvidenceError(
            f"{finding.rule_id}: evidence is not a verbatim span of the draft: {finding.evidence!r}"
        )
    return replace(finding, span=(start, start + len(finding.evidence)))


def run_checks(
    text: str,
    meta: Mapping[str, Any] | None = None,
    rules: Sequence[Rule] | None = None,
) -> list[Finding]:
    """Run every rule over ``text`` and return findings, blocker-first.

    Args:
        text: The draft submission, verbatim.
        meta: Side facts the draft cannot state about itself -- ``links``,
            ``required_links``, ``hard_rules``. Never mutated.
        rules: Override the registry (used by tests).

    Raises:
        EvidenceError: A rule quoted something that is not in the draft.
        RuleError: A rule is malformed.
    """
    facts: Mapping[str, Any] = dict(meta or {})
    active = tuple(rules) if rules is not None else registry()

    collected: list[tuple[Finding, int]] = []
    for index, rule in enumerate(active):
        for raw in rule(text, facts):
            collected.append((_validate(raw, text, rule), index))

    seen: set[tuple] = set()
    unique: list[tuple[Finding, int]] = []
    for finding, idx in collected:
        key = (finding.rule_id, finding.severity, finding.title, finding.evidence, finding.span)
        if key in seen:
            continue
        seen.add(key)
        unique.append((finding, idx))

    unique.sort(key=lambda pair: (pair[0].rank, pair[0].span[0] if pair[0].span else 1 << 30, pair[1]))
    return [finding for finding, _ in unique]


def format_findings(findings: Sequence[Finding]) -> str:
    """Human-readable report, blocker-first."""
    if not findings:
        return "No findings. Submit it."
    counts = {name: sum(1 for f in findings if f.severity == name) for name in SEVERITIES}
    header = "  ".join(f"{counts[name]} {name}" for name in SEVERITIES if counts[name])
    return "\n\n".join([header, *(f.render() for f in findings)])


def main(argv: Sequence[str] | None = None) -> int:
    import argparse
    import json
    import sys

    parser = argparse.ArgumentParser(description="Check a hackathon submission draft.")
    parser.add_argument("draft", help="path to the draft (markdown or plain text)")
    parser.add_argument("--meta", help="path to a JSON file of links / hard_rules", default=None)
    args = parser.parse_args(argv)

    with open(args.draft, encoding="utf-8") as handle:
        text = handle.read()
    facts: dict[str, Any] = {}
    if args.meta:
        with open(args.meta, encoding="utf-8") as handle:
            facts = json.load(handle)

    findings = run_checks(text, facts)
    print(format_findings(findings))
    return 1 if any(f.severity == BLOCKER for f in findings) else 0


if __name__ == "__main__":
    # Import under the canonical name so the rules register into the same
    # module instance the CLI reads from, not into a second copy.
    import os
    import sys

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from check_engine import main as _main

    raise SystemExit(_main())
