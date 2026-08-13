"""The ten checks from RULES.md, as pure functions.

Every rule is ``(text, meta) -> list[Finding]``: no I/O, no clock, no state.
Every Finding either quotes an exact span of the draft (sliced, never rebuilt)
or quotes nothing at all when the problem is that something is missing.

``meta`` carries only what a draft cannot state about itself:

    {
      "links": {"repo": "...", "live": "...", "video": "..."}  # or a list of URLs
      "required_links": ["repo", "live", "video"],
      "hard_rules": ["a real neurodivergent user in design or testing"],
    }

All keys are optional; rules degrade to what they can honestly check.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, Pattern
from urllib.parse import urlparse

from check_engine import BLOCKER, FRICTION, NOTE, Finding, register

from ._text import Span, headings, lead_end, prose, sentences

# --------------------------------------------------------------------------
# Provenance -- one line per rule, straight from RULES.md. No hypotheticals.
# --------------------------------------------------------------------------

FROM_TEST_COUNT = (
    "ProofPrint / Backblaze (did not place): winners led with '358 executable assertions' "
    "and '485 tests'; ProofPrint had one 122-line script and never mentioned it, while two "
    "of four criteria were about production readiness."
)
FROM_HEADLINE = (
    "ProofPrint: its best number -- a sealed PNG cut 34x to a metadata-stripped JPEG, still "
    "resolved at 0/64 bits -- was item 3 of a sub-list; the Grand Prize winner's first line "
    "was '9.3s vs 65.7s on job j_47cdc2, live, check it yourself.'"
)
FROM_AUDIENCE = (
    "ProofPrint: the only named buyer appeared in the roadmap, while the criterion asked "
    "'is there a clear audience?'"
)
FROM_BUGS = (
    "ProofPrint filed three excellent Genblaze bugs under 'Challenges we ran into'; FirstFrame "
    "filed 3 PRs and an issue with reproductions and failing tests, and led with it."
)
FROM_OPENING = (
    "ProofPrint opened with 'EU AI Act Article 50 became applicable'; FirstFrame opened with "
    "someone waiting four minutes to watch four seconds and say no."
)
FROM_FAILURE = (
    "Backblaze: every winner kept one visible failure -- a retained failed attempt, a TEST FAULT "
    "badge, an UNKNOWN field; perfect surfaces read as untested."
)
FROM_GUARANTEE = (
    "ProofPrint probed Object Lock at startup; FirstFrame issued a real delete and asserted "
    "the refusal."
)
FROM_LINKS = "Repo, live URL, demo video: mechanical, and people still lose on it."
FROM_HARD_RULES = (
    "IncludAI: over half the field broke a hard rule (a real neurodivergent user in design "
    "or testing)."
)
FROM_NO_KEY = (
    "Backblaze: three strong entries made 'works with no API key' a headline; it removes the "
    "biggest reason a judge never tries your project."
)


def _evidence(span: Span) -> dict[str, Any]:
    text, offsets = span.as_evidence()
    return {"evidence": text, "span": offsets}


def _summarize(text: str, limit: int = 90) -> str:
    """Squash a phrase onto one line so it can be embedded in a title or fix."""
    flat = " ".join(text.split()).rstrip(".")
    flat = flat.replace(". ", "; ")
    if len(flat) > limit:
        cut = flat.rfind(" ", 0, limit)
        flat = flat[: cut if cut > 0 else limit].rstrip(",;") + "..."
    return flat


# --------------------------------------------------------------------------
# 1. No test count stated
# --------------------------------------------------------------------------

_TEST_COUNT = re.compile(
    r"""(?:
        \b\d[\d,]*\s+(?:\w+\s+){0,2}?(?:assertions?|tests?|test\s+cases?|checks?|specs?|scenarios?)\b
      | \b(?:assertions?|tests?|checks?|specs?)\s*[:=]\s*\d[\d,]*
      | \b\d[\d,]*\s+(?:passing|green|executable)\b
    )""",
    re.I | re.X,
)
_TESTING_MENTIONED = re.compile(
    r"\b(?:tests?|tested|testing|test\s+suite|assertions?|coverage|pytest|unittest|CI)\b", re.I
)


@register("no-test-count")
def no_test_count(text: str, meta: Mapping[str, Any]) -> list[Finding]:
    """Blocker unless the draft states how many tests or assertions exist."""
    if _TEST_COUNT.search(text):
        return []

    spans = prose(text)
    mention = next((span for span in spans if _TESTING_MENTIONED.search(span.text)), None)
    quoted = _evidence(mention) if mention else {"evidence": "", "span": None}
    title = (
        "Testing is mentioned but never counted"
        if mention
        else "No test or assertion count anywhere in the draft"
    )
    return [
        Finding(
            rule_id="no-test-count",
            severity=BLOCKER,
            title=title,
            fix="State the exact number of executable tests or assertions and where they run.",
            provenance=FROM_TEST_COUNT,
            **quoted,
        )
    ]


# --------------------------------------------------------------------------
# 2. Headline number buried
# --------------------------------------------------------------------------

_NUMERIC_CLAIMS: tuple[tuple[Pattern[str], int], ...] = (
    (
        re.compile(
            r"\d[\d,]*(?:\.\d+)?\s*(?:ms|s|secs?|seconds?|mins?|minutes?|hours?)\b"
            r"[^.\n]{0,40}?\bvs\.?\b[^.\n]{0,40}?\d",
            re.I,
        ),
        5,
    ),
    (re.compile(r"\b\d[\d,]*(?:\.\d+)?\s*[x×]\b", re.I), 4),
    (re.compile(r"\b\d[\d,]*\s*/\s*\d[\d,]*\b"), 4),
    (re.compile(r"\b\d[\d,]*(?:\.\d+)?\s*(?:ms|secs?|seconds?|minutes?)\b", re.I), 3),
    (re.compile(r"\b\d[\d,]*(?:\.\d+)?\s*%"), 2),
    (re.compile(r"\b\d{3,}\b"), 1),
)


def _claim_score(sentence: str) -> int:
    return max((score for pattern, score in _NUMERIC_CLAIMS if pattern.search(sentence)), default=0)


@register("headline-number-buried")
def headline_number_buried(text: str, meta: Mapping[str, Any]) -> list[Finding]:
    """Blocker unless the draft's strongest number sits in the opening lines."""
    spans = prose(text)
    if not spans:
        return []

    best: Span | None = None
    best_score = 0
    for span in spans:
        score = _claim_score(span.text)
        if score > best_score:
            best, best_score = span, score

    if best is None:
        return [
            Finding(
                rule_id="headline-number-buried",
                severity=BLOCKER,
                title="No measured result number anywhere in the draft",
                evidence="",
                fix="Measure the one thing the project does best and open with that number.",
                provenance=FROM_HEADLINE,
            )
        ]

    opening = lead_end(spans, 3)
    if best.start < opening:
        return []

    where = "in a sub-list" if best.depth >= 2 else "below the opening"
    return [
        Finding(
            rule_id="headline-number-buried",
            severity=BLOCKER,
            title=f"Best number is buried {where}",
            fix="Move this number into the first two lines of the submission.",
            provenance=FROM_HEADLINE,
            **_evidence(best),
        )
    ]


# --------------------------------------------------------------------------
# 3. Audience deferred to "What's next"
# --------------------------------------------------------------------------

_FUTURE_HEADING = re.compile(
    r"\b(?:what'?s\s+next|next\s+steps?|roadmap|future(?:\s+work|\s+plans)?|coming\s+soon"
    r"|beyond\s+the\s+hackathon|after\s+the\s+hackathon|where\s+(?:we|this)\s+go(?:es)?\s+next)\b",
    re.I,
)
_AUDIENCE = re.compile(
    r"""\b(?:
        built\s+for | designed\s+for | made\s+for | aimed\s+at | sells?\s+to | ships?\s+to
      | our\s+(?:first\s+)?(?:user|users|customer|customers|buyer|buyers|design\s+partner)
      | target\s+(?:audience|user|users|customer|customers|market)
      | who\s+(?:it'?s|this\s+is|we\s+built\s+it)\s+for
      | (?:the\s+)?(?:audience|buyer|customer|user)\s+is\s+\w
      | for\s+(?:teams|developers|engineers|auditors|clinicians|newsrooms|studios)\b
    )""",
    re.I | re.X,
)


@register("audience-deferred")
def audience_deferred(text: str, meta: Mapping[str, Any]) -> list[Finding]:
    """Blocker if the audience is named only inside a future-work section."""
    spans = sentences(text, include_headings=True)
    named = [span for span in spans if _AUDIENCE.search(span.text)]

    if not named:
        return [
            Finding(
                rule_id="audience-deferred",
                severity=BLOCKER,
                title="No audience named anywhere in the draft",
                evidence="",
                fix="Name the buyer in the first paragraph, not in the roadmap.",
                provenance=FROM_AUDIENCE,
            )
        ]

    first = named[0]
    section = first.text if first.is_heading else first.heading
    if not _FUTURE_HEADING.search(section or ""):
        return []

    return [
        Finding(
            rule_id="audience-deferred",
            severity=BLOCKER,
            title=f"Audience appears only under '{_summarize(section, 40)}'",
            fix="Move the audience out of the roadmap and into the opening paragraph.",
            provenance=FROM_AUDIENCE,
            **_evidence(first),
        )
    ]


# --------------------------------------------------------------------------
# 4. SDK bugs written as complaints
# --------------------------------------------------------------------------

_CHALLENGE_HEADING = re.compile(
    r"\b(?:challenges?|what\s+went\s+wrong|problems?|blockers?|pain\s+points?|obstacles"
    r"|difficulties|struggles?)\b",
    re.I,
)
_BUG_LANGUAGE = re.compile(
    r"""\b(?:
        bugs? | broken | crash(?:ed|es)? | undocumented | regression | panics?
      | silently\s+(?:fails?|failed|drops?) | fails?\s+silently
      | (?:did\s?n'?t|does\s?n'?t|would\s?n'?t)\s+work
      | (?:lost|burned|wasted)\s+\w+\s+(?:hours?|days?)
      | fought\s+with | wrestled\s+with | kept\s+returning | returned\s+a\s+\d{3}
    )\b""",
    re.I | re.X,
)
_CONTRIBUTION = re.compile(
    r"""(?:
        \bpull\s+requests?\b | \bPRs?\b | \bfiled\b | \bopened\s+(?:an?\s+)?issue\b
      | \bissue\s*\#?\d+ | \bminimal\s+repro(?:duction)?\b | \brepro\b
      | \bfailing\s+test\b | \bupstream(?:ed)?\b | \bpatch(?:ed|es)?\b | \breported\s+it\b
    )""",
    re.I | re.X,
)


@register("bugs-as-complaints")
def bugs_as_complaints(text: str, meta: Mapping[str, Any]) -> list[Finding]:
    """Friction when SDK bugs are filed under 'Challenges' with no PR or issue."""
    if _CONTRIBUTION.search(text):
        return []

    complaint = next(
        (
            span
            for span in prose(text)
            if _CHALLENGE_HEADING.search(span.heading or "") and _BUG_LANGUAGE.search(span.text)
        ),
        None,
    )
    if complaint is None:
        return []

    return [
        Finding(
            rule_id="bugs-as-complaints",
            severity=FRICTION,
            title="Upstream bug written up as a complaint, not a contribution",
            fix="File the bug upstream with a reproduction and a failing test, then lead with that.",
            provenance=FROM_BUGS,
            **_evidence(complaint),
        )
    ]


# --------------------------------------------------------------------------
# 5. Opens with a regulation, not a person
# --------------------------------------------------------------------------

_ABSTRACT_OPENING = re.compile(
    r"""\b(?:
        article\s+\d+ | eu\s+ai\s+act | gdpr | hipaa | ccpa | soc\s?2 | dsa\b
      | regulations? | regulatory | directive | legislation | statutory
      | compliance\s+(?:mandate|requirement|deadline)s?
      | the\s+[A-Z]\w+\s+Act\b | came\s+into\s+force | becomes?\s+applicable | became\s+applicable
      | the\s+(?:global\s+)?market\s+for | total\s+addressable\s+market
      | according\s+to\s+(?:gartner|forrester|idc|mckinsey)
      | \d{1,3}\s?%\s+of\s+(?:companies|enterprises|organi[sz]ations|developers|teams)
    )\b""",
    re.I | re.X,
)
_PERSON_WORD = re.compile(
    r"""\b(?:
        someone | somebody | anyone | a\s+(?:developer|designer|engineer|user|judge|founder
      | reviewer|creator|editor|producer|shopper|patient|nurse|teacher|student|parent|customer
      | admin|kid|friend|stranger|buyer)
    )\b""",
    re.I | re.X,
)
_PERSON_NAME = re.compile(
    r"\b[A-Z][a-z]{2,}\s+(?:waited|watched|opened|clicked|spent|stared|uploaded|paid|gave"
    r"|asked|read|called|sat|tried|needed|wanted|refused|quit)\b"
)


@register("opens-with-abstraction")
def opens_with_abstraction(text: str, meta: Mapping[str, Any]) -> list[Finding]:
    """Friction when the first sentence is a regulation or a market, not a person."""
    spans = prose(text)
    if not spans:
        return []

    opening = spans[0]
    if not _ABSTRACT_OPENING.search(opening.text):
        return []
    if _PERSON_WORD.search(opening.text) or _PERSON_NAME.search(opening.text):
        return []

    return [
        Finding(
            rule_id="opens-with-abstraction",
            severity=FRICTION,
            title="Opens with a regulation or a market, not a person",
            fix="Open with one person hitting the problem in a specific moment.",
            provenance=FROM_OPENING,
            **_evidence(opening),
        )
    ]


# --------------------------------------------------------------------------
# 6. No visible failure
# --------------------------------------------------------------------------

_FAILURE_BADGE = re.compile(
    r"\b(?:FAIL|FAILED|FAILURE|FAULT|UNKNOWN|DENIED|REFUSED|TIMEOUT|SKIPPED|RED)\b"
)  # case-sensitive: an uppercase badge is a surfaced state, not prose
_FAILURE_PHRASE = re.compile(
    r"""\b(?:
        failed\s+attempts? | retained\s+(?:the\s+)?fail\w* | kept\s+the\s+fail\w*
      | known\s+limitations? | limitations? | caveats? | rough\s+edges?
      | (?:does|did)\s+not\s+work | (?:does|did)\s?n'?t\s+work
      | we\s+could\s?n'?t | we\s+can\s?n?'?t | not\s+supported | unsupported
      | fails?\s+(?:when|if|on|for|silently) | silently\s+fails?
      | times?\s+out | timed\s+out | access\s?denied | falls?\s+back
      | still\s+broken | open\s+bug | what\s+does\s?n'?t\s+work
    )\b""",
    re.I | re.X,
)
_FAILURE_HEADING = re.compile(
    r"\b(?:limitations?|known\s+issues?|what\s+does\s?n'?t\s+work|failures?|caveats?"
    r"|rough\s+edges?|not\s+supported)\b",
    re.I,
)
_PERFECTION = re.compile(
    r"""\b(?:
        every\s+(?:run|time|case|test|file|upload) | always | 100\s?% | never\s+fails?
      | flawless(?:ly)? | seamless(?:ly)? | perfectly | zero\s+(?:errors|failures|bugs)
      | no\s+(?:errors|failures) | works\s+every\s+time | rock\s+solid
    )\b""",
    re.I | re.X,
)


@register("no-visible-failure")
def no_visible_failure(text: str, meta: Mapping[str, Any]) -> list[Finding]:
    """Friction when nothing in the draft shows the system failing."""
    if _FAILURE_BADGE.search(text) or _FAILURE_PHRASE.search(text):
        return []
    if any(_FAILURE_HEADING.search(head.text) for head in headings(text)):
        return []

    boast = next((span for span in prose(text) if _PERFECTION.search(span.text)), None)
    quoted = _evidence(boast) if boast else {"evidence": "", "span": None}
    title = (
        "Perfect surface: nothing in the draft ever fails"
        if boast
        else "No failure is ever shown"
    )
    return [
        Finding(
            rule_id="no-visible-failure",
            severity=FRICTION,
            title=title,
            fix="Keep one real failure visible in the demo and name it in the draft.",
            provenance=FROM_FAILURE,
            **quoted,
        )
    ]


# --------------------------------------------------------------------------
# 7. Guarantee asserted, never attacked
# --------------------------------------------------------------------------

_GUARANTEE = re.compile(
    r"""(?:
        \bguarantee[sd]?\b | \bimmutab(?:le|ility)\b | \btamper[-\s]?(?:proof|evident)\b
      | \bcan(?:not|'?t)\s+be\s+(?:deleted|modified|altered|overwritten|forged)\b
      | \bwrite[-\s]?once\b | \bWORM\b | \bobject\s+lock\b | \bappend[-\s]?only\b
      | \bunforgeable\b | \bimpossible\s+to\s+(?:forge|delete|fake|alter)\b
      | \bprovabl[ye]\b | \benforced\s+by\b | \bsealed\s+for\s+good\b
    )""",
    re.I | re.X,
)
_ATTACKED = re.compile(
    r"""(?:
        \bwe\s+(?:tried|attempted|issued|ran|sent|fired)\s+(?:a\s+|an\s+)?(?:real\s+)?
          (?:delete|deletion|overwrite|attack|forgery|tamper)
      | \bissued\s+a\s+(?:real\s+)?delete\b | \battempted\s+(?:to\s+)?(?:delete|overwrite|forge|tamper)\b
      | \badversarial\b | \bred[-\s]?team(?:ed|ing)?\b | \battack(?:ed|s)?\b
      | \bassert(?:ed|s)?\s+the\s+(?:refusal|denial|rejection|error)\b
      | \baccess\s?denied\b | \b403\b | \bthe\s+delete\s+(?:was\s+)?(?:refused|denied|rejected)\b
      | \bwe\s+deleted\b | \btampered\b | \bflipped\s+a\s+bit\b | \bnegative\s+tests?\b
      | \bproved\s+it\s+by\s+trying\b
    )""",
    re.I | re.X,
)


@register("guarantee-unattacked")
def guarantee_unattacked(text: str, meta: Mapping[str, Any]) -> list[Finding]:
    """Friction when a hard guarantee is claimed but never attacked on camera."""
    if _ATTACKED.search(text):
        return []

    claim = next((span for span in prose(text) if _GUARANTEE.search(span.text)), None)
    if claim is None:
        return []

    return [
        Finding(
            rule_id="guarantee-unattacked",
            severity=FRICTION,
            title="Guarantee is asserted but never attacked",
            fix="Attack the guarantee on camera and assert the refusal it returns.",
            provenance=FROM_GUARANTEE,
            **_evidence(claim),
        )
    ]


# --------------------------------------------------------------------------
# 8. Required links missing
# --------------------------------------------------------------------------

_URL = re.compile(r"https?://[^\s)>\]\"'`]+")
_REPO_HOSTS = ("github.com", "gitlab.com", "bitbucket.org", "codeberg.org", "git.sr.ht")
_VIDEO_HOSTS = ("youtube.com", "youtu.be", "vimeo.com", "loom.com", "wistia.com", "streamable.com")
_NOT_LIVE_HOSTS = ("devpost.com", "twitter.com", "x.com", "linkedin.com", "discord.gg", "t.me")
_LINK_LABELS = {"repo": "Repo link", "live": "Live URL", "video": "Demo video link"}
_DEFAULT_REQUIRED = ("repo", "live", "video")


def _classify(url: str) -> str | None:
    host = (urlparse(url).netloc or "").lower().removeprefix("www.")
    if not host:
        return None
    if any(host == h or host.endswith("." + h) for h in _REPO_HOSTS):
        return "repo"
    if any(host == h or host.endswith("." + h) for h in _VIDEO_HOSTS):
        return "video"
    if url.lower().rsplit(".", 1)[-1] in ("mp4", "mov", "webm"):
        return "video"
    if any(host == h or host.endswith("." + h) for h in _NOT_LIVE_HOSTS):
        return None
    return "live"


@register("required-links-missing")
def required_links_missing(text: str, meta: Mapping[str, Any]) -> list[Finding]:
    """One blocker per missing required link. Mechanical, and people still lose on it."""
    present: set[str] = set()

    links = meta.get("links") or {}
    if isinstance(links, Mapping):
        for kind, url in links.items():
            if url and str(url).strip():
                present.add(str(kind).lower())
    else:
        for url in links:
            kind = _classify(str(url))
            if kind:
                present.add(kind)

    for url in _URL.findall(text):
        kind = _classify(url)
        if kind:
            present.add(kind)

    required = meta.get("required_links") or _DEFAULT_REQUIRED
    return [
        Finding(
            rule_id="required-links-missing",
            severity=BLOCKER,
            title=f"{_LINK_LABELS.get(str(kind).lower(), str(kind))} missing",
            evidence="",
            fix=f"Add the {_LINK_LABELS.get(str(kind).lower(), str(kind)).lower()} to the submission form.",
            provenance=FROM_LINKS,
        )
        for kind in required
        if str(kind).lower() not in present
    ]


# --------------------------------------------------------------------------
# 9. Rules not read
# --------------------------------------------------------------------------

_STOPWORDS = frozenset(
    """a an and are as at be been by for from has have in into is it its must not of on or
    should that the their there they this to was were will with you your each every all any
    real used using use include includes including least most than then when which who whose
    entry entries submission submissions team teams project projects please ensure""".split()
)
_WORD = re.compile(r"[A-Za-z][A-Za-z'\-]+")
_STEM = 5


def _distinctive(requirement: str, limit: int = 3) -> list[str]:
    words = [w.lower() for w in _WORD.findall(requirement) if len(w) > 3]
    keywords = [w for w in words if w not in _STOPWORDS]
    seen: set[str] = set()
    unique = [w for w in keywords if not (w in seen or seen.add(w))]
    return sorted(unique, key=len, reverse=True)[:limit]


@register("hard-rules-unaddressed")
def hard_rules_unaddressed(text: str, meta: Mapping[str, Any]) -> list[Finding]:
    """Blocker per hard rule the draft never addresses; note when no rules were recorded.

    A rule counts as addressed when its most distinctive word appears in the draft
    and at least half of its distinctive words do -- so a passing mention of the
    topic is not mistaken for having satisfied the requirement.
    """
    requirements = [str(r) for r in (meta.get("hard_rules") or []) if str(r).strip()]
    if not requirements:
        return [
            Finding(
                rule_id="hard-rules-unaddressed",
                severity=NOTE,
                title="No hard rules recorded to check against",
                evidence="",
                fix="Paste the hackathon's hard requirements into meta['hard_rules'] and re-run.",
                provenance=FROM_HARD_RULES,
            )
        ]

    lowered = text.lower()
    findings: list[Finding] = []
    for requirement in requirements:
        keywords = _distinctive(requirement)
        if not keywords:
            continue
        hits = [keyword for keyword in keywords if keyword[:_STEM] in lowered]
        if keywords[0] in hits and len(hits) * 2 >= len(keywords):
            continue
        short = _summarize(requirement, 70)
        findings.append(
            Finding(
                rule_id="hard-rules-unaddressed",
                severity=BLOCKER,
                title=f"Hard rule unaddressed: {short}",
                evidence="",
                fix=f"Say in the draft how the entry satisfies the rule: {short}.",
                provenance=FROM_HARD_RULES,
            )
        )
    return findings


# --------------------------------------------------------------------------
# 10. "Works with no API key" not said up front
# --------------------------------------------------------------------------

_NO_KEY = re.compile(
    r"""(?:
        \bno\s+api\s+keys?\b | \bwithout\s+an?\s+api\s+key\b | \bno\s+key\s+(?:required|needed)\b
      | \bno\s+(?:sign[-\s]?up|signup|account|credentials?|tokens?)\s+(?:required|needed)\b
      | \bzero[-\s]config\b | \bno\s+setup\b | \bworks\s+offline\b | \bruns\s+offline\b
      | \bno\s+external\s+services?\b
    )""",
    re.I | re.X,
)


@register("no-api-key-not-upfront")
def no_api_key_not_upfront(text: str, meta: Mapping[str, Any]) -> list[Finding]:
    """Friction when the keyless claim is buried; a note when it is never made."""
    spans = prose(text)
    if not spans:
        return []

    claim = next((span for span in spans if _NO_KEY.search(span.text)), None)
    if claim is None:
        return [
            Finding(
                rule_id="no-api-key-not-upfront",
                severity=NOTE,
                title="Never says whether a judge needs an API key",
                evidence="",
                fix="Say 'runs with no API key' in the first two lines if it is true.",
                provenance=FROM_NO_KEY,
            )
        ]

    if claim.start < lead_end(spans, 3):
        return []

    return [
        Finding(
            rule_id="no-api-key-not-upfront",
            severity=FRICTION,
            title="Keyless setup is claimed too late to matter",
            fix="Move the no-API-key claim into the first two lines.",
            provenance=FROM_NO_KEY,
            **_evidence(claim),
        )
    ]
