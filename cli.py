#!/usr/bin/env python3
"""submission-check — read a hackathon draft, print what will lose it.

    python cli.py draft.md
    python cli.py draft.md --json
    python cli.py draft.md --score

Stdlib only. Zero dependencies, zero API keys, no network calls.

The rules live in ``rules/checks.py``; ``check_engine`` runs them over the
document. This module is the presentation layer — it normalises whatever the
engine returns and renders it grouped into blockers, friction and notes, each
finding carrying three things: the quoted evidence from your draft, a one-line
fix, and the provenance of the rule (which submission lost, and how).

Engine contract
---------------
``check_engine.run_checks(text)`` returns findings, blocker-first. A finding
carries a rule id, a severity, a title, an exact quoted span of the draft (or
``""`` when the problem is an absence and there is honestly nothing to quote),
a one-line fix, the rule's provenance, and the ``(start, end)`` offsets of the
evidence — which is where the line numbers in the report come from. Field
names are read through ``_FIELDS`` so the report survives small differences in
the engine's shape. If the engine grows a ``score(findings)`` that score wins;
otherwise the deduction table in ``compute_score`` applies.
"""

import argparse
import inspect
import json
import os
import shutil
import sys
import textwrap

SEVERITIES = ("blocker", "friction", "note")

# What the engine may call a severity -> what we group it under.
SEVERITY_ALIASES = {
    "blocker": "blocker",
    "block": "blocker",
    "critical": "blocker",
    "error": "blocker",
    "high": "blocker",
    "fatal": "blocker",
    "friction": "friction",
    "warning": "friction",
    "warn": "friction",
    "medium": "friction",
    "note": "note",
    "info": "note",
    "low": "note",
    "nit": "note",
}

HEADINGS = {
    "blocker": ("BLOCKERS", "a judge stops reading, or a criterion scores zero"),
    "friction": ("FRICTION", "costs you points, not the round"),
    "note": ("NOTES", "worth a minute if you have one"),
}

# "friction" is a mass noun; the other two count.
PLURALS = {"blocker": "blockers", "friction": "friction", "note": "notes"}

# Points deducted per finding when the engine does not score for itself.
WEIGHTS = {"blocker": 15, "friction": 6, "note": 2}

# Finding field -> the names an engine might have used for it.
_FIELDS = {
    "rule": ("rule_id", "rule", "id", "check_id", "code"),
    "severity": ("severity", "level", "kind"),
    "title": ("title", "name", "summary", "message"),
    "evidence": ("evidence", "quote", "excerpt", "snippet"),
    "span": ("span", "offsets", "range"),
    "fix": ("fix", "one_line_fix", "suggestion", "remedy"),
    "provenance": ("provenance", "source", "origin", "came_from"),
}

ENGINE_ENTRY_POINTS = ("run_checks", "analyze", "run", "check", "check_document")


class EngineMissing(Exception):
    """Raised when check_engine is absent or exposes no usable entry point."""


def _read(obj, key):
    """Pull one normalised field off a finding, dict or object alike."""
    for name in _FIELDS[key]:
        if isinstance(obj, dict):
            if name in obj and obj[name] is not None:
                return obj[name]
        elif getattr(obj, name, None) is not None:
            return getattr(obj, name)
    return None


def normalise(raw, text=""):
    """Turn one engine finding into the flat dict the report and --json use.

    ``text`` is the draft, used to turn the engine's character offsets into the
    line number a writer can actually navigate to.
    """
    severity = str(_read(raw, "severity") or "note").strip().lower()
    span = _read(raw, "span")
    start = span[0] if isinstance(span, (tuple, list)) and len(span) == 2 else None
    return {
        "rule": str(_read(raw, "rule") or "unknown"),
        "severity": SEVERITY_ALIASES.get(severity, "note"),
        "title": str(_read(raw, "title") or "(untitled check)"),
        "line": text.count("\n", 0, start) + 1 if start is not None else None,
        "span": list(span) if start is not None else None,
        "evidence": _clean(_read(raw, "evidence")),
        "fix": _clean(_read(raw, "fix")),
        "provenance": _clean(_read(raw, "provenance")),
    }


def _clean(value):
    """Collapse a quoted span to a single line of text."""
    if value is None:
        return ""
    return " ".join(str(value).split())


def load_engine():
    """Import check_engine and return (run_fn, score_fn_or_None)."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        import check_engine
    except ImportError as exc:
        raise EngineMissing(
            "check_engine is not importable (%s). It should sit next to cli.py, "
            "alongside the rules package in rules/checks.py." % exc
        )
    for name in ENGINE_ENTRY_POINTS:
        run = getattr(check_engine, name, None)
        if callable(run):
            return run, getattr(check_engine, "score", None)
    raise EngineMissing(
        "check_engine exposes none of: %s" % ", ".join(ENGINE_ENTRY_POINTS)
    )


def run_engine(run, text, path):
    """Call the engine, passing the draft path only if it asks for one."""
    if "path" in inspect.signature(run).parameters:
        return run(text, path=path)
    return run(text)


def compute_score(findings):
    """0-100. Starts at 100; every finding deducts by severity, floored at 0."""
    lost = sum(WEIGHTS[f["severity"]] for f in findings)
    return max(0, 100 - lost)


def count_by_severity(findings):
    return {s: sum(1 for f in findings if f["severity"] == s) for s in SEVERITIES}


def analyse(path):
    """Read a draft, run the engine over it, return the normalised report."""
    with open(path, encoding="utf-8") as handle:
        text = handle.read()

    run, engine_score = load_engine()
    findings = [normalise(f, text) for f in (run_engine(run, text, path) or [])]
    findings.sort(key=lambda f: (SEVERITIES.index(f["severity"]), f["line"] or 0))

    score = engine_score(findings) if callable(engine_score) else compute_score(findings)
    return {
        "path": path,
        "score": int(score),
        "counts": count_by_severity(findings),
        "findings": findings,
    }


class Style:
    """ANSI when we are talking to a terminal, plain text otherwise."""

    def __init__(self, enabled):
        self.enabled = enabled

    def __call__(self, text, code):
        return "\033[%sm%s\033[0m" % (code, text) if self.enabled else text

    def bold(self, text):
        return self(text, "1")

    def dim(self, text):
        return self(text, "2")

    def severity(self, text, severity):
        return self(text, {"blocker": "31", "friction": "33", "note": "36"}[severity])


def render(report, style):
    """The human report: grouped, evidence first, fix second, provenance last."""
    width = min(shutil.get_terminal_size((88, 24)).columns, 88)
    counts = report["counts"]
    out = []

    summary = " · ".join(
        "%d %s" % (counts[s], s if counts[s] == 1 else PLURALS[s]) for s in SEVERITIES
    )
    out.append("")
    out.append(style.bold(report["path"]))
    out.append("%s   %s" % (style.bold("score %d/100" % report["score"]), summary))

    if not report["findings"]:
        out.append("")
        out.append("Nothing caught. Every rule in RULES.md passed.")
        out.append("")
        return "\n".join(out)

    for severity in SEVERITIES:
        group = [f for f in report["findings"] if f["severity"] == severity]
        if not group:
            continue
        heading, gloss = HEADINGS[severity]
        out.append("")
        out.append(
            "%s  %s" % (style.severity(heading, severity), style.dim("— " + gloss))
        )
        out.append("")
        for index, finding in enumerate(group, 1):
            out.extend(_render_finding(index, finding, style, width))
    out.append("")
    return "\n".join(out)


def _render_finding(index, finding, style, width):
    """One finding: title + rule id, then evidence / fix / why."""
    lines = []
    title = "%2d. %s" % (index, finding["title"])
    rule = style.dim("[%s]" % finding["rule"])
    pad = max(1, width - len(title) - len(finding["rule"]) - 2)
    lines.append("  " + title + " " * pad + rule)

    if finding["evidence"]:
        where = "line %d: " % finding["line"] if finding["line"] else ""
        lines.extend(_field("evidence", where + '"%s"' % finding["evidence"], style, width))
    else:
        # An absence: the draft never says it, so there is nothing to quote.
        lines.extend(_field("evidence", "(nothing to quote — it is missing)", style, width))
    if finding["fix"]:
        lines.extend(_field("fix", finding["fix"], style, width))
    if finding["provenance"]:
        lines.extend(_field("why", finding["provenance"], style, width, dim=True))
    lines.append("")
    return lines


def _field(label, value, style, width, dim=False):
    """A wrapped, hanging-indented ``label  value`` block."""
    indent = " " * 16
    body = textwrap.wrap(value, width=max(40, width - len(indent))) or [""]
    head = "      %-9s %s" % (style.dim(label), body[0])
    rest = [indent + line for line in body[1:]]
    if dim:
        head = "      %-9s %s" % (style.dim(label), style.dim(body[0]))
        rest = [indent + style.dim(line) for line in body[1:]]
    return [head] + rest


def build_parser():
    parser = argparse.ArgumentParser(
        prog="cli.py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Read a hackathon submission draft and print what will lose it, "
            "grouped into blockers, friction and notes. Every finding shows the "
            "quoted evidence from your draft, a one-line fix, and where the rule "
            "came from (a real submission that lost, see RULES.md)."
        ),
        epilog=(
            "Zero dependencies, zero API keys. Python standard library only —\n"
            "nothing is uploaded, no network call is made, no model is queried.\n"
            "Your draft never leaves the machine.\n"
            "\n"
            "exit status: 0 if no blockers, 1 if any blocker, 2 on a usage or\n"
            "read error — so it drops straight into a pre-submit check.\n"
            "\n"
            "examples:\n"
            "  python cli.py draft.md\n"
            "  python cli.py draft.md --json | jq '.findings[] | select(.severity==\"blocker\")'\n"
            "  test $(python cli.py draft.md --score) -ge 70 || echo 'not ready'\n"
        ),
    )
    parser.add_argument("draft", help="path to the submission draft (markdown)")
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit the full report as JSON instead of the human report",
    )
    parser.add_argument(
        "--score",
        action="store_true",
        help="print only the score, 0-100 (100 is clean; every finding deducts)",
    )
    parser.add_argument(
        "--no-color", action="store_true", help="disable ANSI colour in the report"
    )
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        report = analyse(args.draft)
    except EngineMissing as exc:
        parser.exit(2, "cli.py: %s\n" % exc)
    except OSError as exc:
        parser.exit(2, "cli.py: cannot read %s: %s\n" % (args.draft, exc.strerror))

    if args.json:
        print(json.dumps(report, indent=2))
    elif args.score:
        print(report["score"])
    else:
        colour = sys.stdout.isatty() and not args.no_color and "NO_COLOR" not in os.environ
        print(render(report, Style(colour)))

    return 1 if report["counts"]["blocker"] else 0


if __name__ == "__main__":
    sys.exit(main())
