"""Offset-preserving reading of a markdown draft.

Every Span this module returns is an exact slice of the draft: ``doc[s.start:s.end]
== s.text``. Rules quote spans and nothing else, which is how "never invent
evidence" is guaranteed rather than merely intended.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Iterable, Iterator, Pattern

_HEADING = re.compile(r"^\s*(#{1,6})\s+(.*?)\s*$")
_FENCE = re.compile(r"^\s*(?:```|~~~)")
_LIST = re.compile(r"^(\s*)(?:[-*+]|\d+[.)])\s+")
_QUOTE = re.compile(r"^\s*>+\s?")
_INDENT = re.compile(r"^\s+")
_SENTENCE_BREAK = re.compile(r"(?<=[.!?])[\"'’)\]]*\s+")
_EMPHASIS_OPEN = re.compile(r"^(?:\*\*|__|\*|_|`)+")
_EMPHASIS_CLOSE = re.compile(r"(?:\*\*|__|\*|_|`)+$")


@dataclass(frozen=True)
class Span:
    """A verbatim slice of the draft, plus where it sits in the document."""

    start: int
    end: int
    text: str
    heading: str = ""  # nearest preceding heading (a heading's own title, for headings)
    depth: int = 0  # list nesting: 0 = paragraph, 1 = top-level bullet, 2+ = sub-list
    is_heading: bool = False

    def clip(self, limit: int = 400) -> "Span":
        """Narrow to at most ``limit`` chars at a word boundary, staying exact."""
        if len(self.text) <= limit:
            return self
        cut = self.text.rfind(" ", 0, limit)
        if cut <= 0:
            cut = limit
        return replace(self, end=self.start + cut, text=self.text[:cut])

    def as_evidence(self) -> tuple[str, tuple[int, int]]:
        clipped = self.clip()
        return clipped.text, (clipped.start, clipped.end)


def _iter_lines(doc: str) -> Iterator[tuple[int, str]]:
    offset = 0
    for line in doc.split("\n"):
        yield offset, line
        offset += len(line) + 1


def _strip_markers(doc: str, start: int, end: int) -> tuple[int, int, int]:
    """Advance past blockquote / list / indent markers. Returns (start, end, depth)."""
    depth = 0
    while start < end:
        rest = doc[start:end]
        quoted = _QUOTE.match(rest)
        if quoted and quoted.end():
            start += quoted.end()
            continue
        listed = _LIST.match(rest)
        if listed:
            depth = len(listed.group(1)) // 2 + 1
            start += listed.end()
            continue
        indent = _INDENT.match(rest)
        if indent:
            start += indent.end()
            continue
        break
    return start, end, depth


def _strip_emphasis(doc: str, start: int, end: int) -> tuple[int, int]:
    opened = _EMPHASIS_OPEN.match(doc[start:end])
    if opened:
        start += opened.end()
    closed = _EMPHASIS_CLOSE.search(doc[start:end])
    if closed:
        end -= len(closed.group(0))
    return start, max(start, end)


def _split_sentences(doc: str, start: int, end: int) -> Iterator[tuple[int, int]]:
    segment = doc[start:end]
    cursor = 0
    for brk in _SENTENCE_BREAK.finditer(segment):
        yield start + cursor, start + brk.start()
        cursor = brk.end()
    yield start + cursor, end


def sentences(doc: str, *, include_headings: bool = False) -> list[Span]:
    """Split ``doc`` into sentence spans, skipping fenced code.

    Headings are excluded by default but always tracked, so every prose span
    knows which section it lives under.
    """
    spans: list[Span] = []
    heading = ""
    in_code = False

    for offset, line in _iter_lines(doc):
        if _FENCE.match(line):
            in_code = not in_code
            continue
        if in_code or not line.strip():
            continue

        head = _HEADING.match(line)
        if head:
            heading = head.group(2).strip().rstrip("#").strip().strip("*_ ").strip()
            if include_headings:
                start = offset + head.start(2)
                end = start + len(head.group(2))
                start, end = _strip_emphasis(doc, start, end)
                if start < end:
                    spans.append(
                        Span(start, end, doc[start:end], heading=heading, is_heading=True)
                    )
            continue

        start, end, depth = _strip_markers(doc, offset, offset + len(line.rstrip()))
        if start >= end:
            continue
        for piece_start, piece_end in _split_sentences(doc, start, end):
            trimmed_start, trimmed_end = _strip_emphasis(doc, piece_start, piece_end)
            while trimmed_start < trimmed_end and doc[trimmed_start].isspace():
                trimmed_start += 1
            while trimmed_end > trimmed_start and doc[trimmed_end - 1].isspace():
                trimmed_end -= 1
            if trimmed_start >= trimmed_end:
                continue
            spans.append(
                Span(
                    trimmed_start,
                    trimmed_end,
                    doc[trimmed_start:trimmed_end],
                    heading=heading,
                    depth=depth,
                )
            )
    return spans


def prose(doc: str) -> list[Span]:
    """Sentence spans excluding headings."""
    return sentences(doc)


def headings(doc: str) -> list[Span]:
    return [span for span in sentences(doc, include_headings=True) if span.is_heading]


def lead_end(spans: Iterable[Span], count: int = 3) -> int:
    """Offset where the opening ends: after the first ``count`` prose sentences."""
    body = [span for span in spans if not span.is_heading]
    if not body:
        return 0
    return body[min(count, len(body)) - 1].end


def first_match(spans: Iterable[Span], pattern: Pattern[str]) -> Span | None:
    """First span matching ``pattern``, in document order."""
    for span in spans:
        if pattern.search(span.text):
            return span
    return None


def matches(spans: Iterable[Span], pattern: Pattern[str]) -> list[Span]:
    return [span for span in spans if pattern.search(span.text)]


def any_match(doc: str, pattern: Pattern[str]) -> bool:
    return bool(pattern.search(doc))
