# The Orchestra — submission text

Paste each block into the matching Devpost field.

---

## Project name

```
submission-check
```

## Short description *(elevator pitch)*

```
Yesterday my hackathon submission lost. The build was competitive; the writeup wasn't. submission-check is the linter I wish I'd run on it — ten checks, every one traced to a specific loss.
```

## Built with

```
python, agent-orchestrator, claude-code, pytest, zero-dependencies
```

---

## Project description

### It found the mistakes that cost me a hackathon yesterday

On 12 August I found out **ProofPrint didn't place** at the Backblaze Generative Media
Hackathon. I spent that evening reading the three winning writeups next to my own, and
the gap wasn't engineering. It was four specific, repeatable mistakes:

- I never stated a test count. Two winners led with **"358 executable assertions"** and
  **"485 tests."**
- My best number — a sealed PNG cut **34×** to a metadata-stripped JPEG that still
  resolved at **0/64 bits** — was item 3 of a sub-list. The Grand Prize winner's
  equivalent was their first line, with a job ID and a live URL.
- I named my audience once, in *"What's next."* The criterion asked *"is there a clear
  audience?"* and I postponed the answer.
- I found three real bugs in the sponsor's SDK and wrote them under *"Challenges we ran
  into."* The winner filed **three pull requests and an issue** with reproductions and
  failing tests — and led with it. Same discovery. Opposite disposition.

**submission-check is those lessons as executable rules.** Paste a draft, get back the
specific things that will cost you placement — each one quoting the exact span that
triggered it, and each one carrying the loss it came from.

### The demo is the proof

**It runs on my own losing submission and finds every mistake that lost it.**

```
$ python cli.py fixtures/proofprint.md
```

Then the control: the same linter on a condensed version of the entry that **won** that
hackathon — and it comes back nearly silent. Two files, same tool, opposite verdicts.

That's not a hypothetical linter. Every rule in `RULES.md` has a provenance column
naming the hackathon it was learned in.


### The one guarantee, enforced rather than promised

Every finding must quote a **verbatim span of your draft**. That isn't a convention the
rules are asked to follow — `run_checks()` enforces it mechanically. A rule that returns
evidence which is not an exact substring of the input raises `EvidenceError` and the run
fails.

```python
class EvidenceError(ValueError):
    """A rule produced evidence that is not a verbatim span of the draft."""
```

So the tool cannot invent a quote to justify a finding, even by accident. Given that its
whole job is telling you your evidence is weak, it seemed fair to hold it to the standard
it enforces.

### Who it's for

Anyone submitting to a hackathon in the next week — and I mean that literally: I have
**seven results pending and nine deadlines in the next nineteen days.** I'm the first
user. This is the tool I run before I press submit tonight.

### Zero dependencies, no API key, no account

Standard library only. `python cli.py draft.md` and it works — offline, on a plane, with
no key to acquire. The checks are pure functions over text; there is no model in the
loop, because a model would make the findings unverifiable, and unverifiable findings are
exactly the problem this tool exists to fix.

### How AO built it

The board tells the story. I registered `submission-check` as an AO project and spawned
worker sessions in isolated git worktrees, each with a scoped brief:

| Session | Task |
|---|---|
| `submission-check-5` | Rule engine + the ten rules + `tests/test_rules.py` |
| `submission-check-6` | CLI, the two real fixtures, `tests/test_fixtures.py` |

Two agents in parallel worktrees, tracked on one Kanban board. The demo shows the board,
not a screenshot of it.

### What went wrong, kept visible

Four earlier worker sessions (`submission-check-1` through `-4`) are terminated on that
board and I've left them there. They died on environment friction — a missing `tmux`, a
folder-trust prompt, and permission dialogs that stalled every agent until I committed a
`.claude/settings.json` the worktrees could inherit. Roughly forty minutes of a
two-and-a-half-hour window.

I'm reporting it because **rule 6 of my own linter is "no visible failure,"** and every
winner I studied yesterday kept one on the page. A perfect surface reads as an untested
one.

### 98 tests

`python -m pytest -q` — 98 tests, no GPU, no network, no key. Every rule has its own
test and both fixtures are asserted end to end.

I am stating the number because **rule 1 of this linter is 'no test count stated'**, and I
lost a hackathon to exactly that omission yesterday.

### Honest limits

It lints **structure and placement**, not truth. It can tell you your headline number is
buried at 68% through the document. It cannot tell you the number is wrong. It flags a
missing test count; it cannot verify the count you write. It is a checklist that learned
from losing — not a judge.

---

## Demo video

```
(paste YouTube link)
```

## Repo

```
https://github.com/Shivang-creator/submission-check
```
