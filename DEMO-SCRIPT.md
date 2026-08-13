# Demo video — 3 minutes

**Rule 8: the video must show your AO Kanban board.** So it opens there, not on the code.

**Before recording:** AO window open on the `submission-check` board with all six
sessions visible (including the four terminated ones — leave them). A terminal in
`~/Projects/submission-check`. Nothing pre-typed.

---

### 0:00 – 0:25 · Open on the board

*Screen: the AO Kanban board.*

> "This is Agent Orchestrator. Two worker sessions built this project in parallel git
> worktrees — one wrote the rule engine and the ten checks, one wrote the CLI and the
> fixtures.
>
> And these four" — *point at the terminated sessions* — "died. Missing tmux, a
> folder-trust prompt, permission dialogs that stalled every agent. About forty minutes
> of a two-and-a-half hour window. I've left them on the board on purpose, and I'll come
> back to why."

### 0:25 – 0:55 · The reason the tool exists

*Screen: terminal, or the Devpost writeup.*

> "Yesterday I found out my submission to the Backblaze hackathon didn't place. I read
> the three winning writeups next to mine that night.
>
> The gap wasn't engineering. I never stated a test count — two winners led with 358
> assertions and 485 tests. My best number was buried at item three of a sub-list; the
> grand prize winner's was their first line. I named my audience once, in 'What's next.'
> And I found three real bugs in the sponsor's SDK and filed them as *complaints* —
> the winner filed three pull requests and led with it."

### 0:55 – 1:50 · Run it on the submission that lost

*Type it live. Don't paste.*

```bash
python cli.py fixtures/proofprint.md
```

> "This is my own losing submission. Every finding quotes the exact span that triggered
> it, gives one fix, and names the hackathon the rule was learned in.
>
> No test count. Headline number at sixty-eight percent through the document. Audience
> deferred. SDK bugs under 'Challenges' with no pull request anywhere near them.
>
> It found the four mistakes that cost me the placement."

### 1:50 – 2:20 · The control

```bash
python cli.py fixtures/firstframe.md
```

> "Same linter, the entry that won that hackathon. Nearly silent.
>
> Two files, one tool, opposite verdicts. That's the whole proof."

### 2:20 – 2:45 · What it is, honestly

```bash
python -m pytest -q
```

> "N tests. Zero dependencies, no API key, no account — standard library only, runs
> offline. There's no model in the loop, deliberately: a model would make the findings
> unverifiable, and unverifiable findings are the problem this thing exists to fix.
>
> It lints structure and placement, not truth. It can tell you your number is buried. It
> can't tell you the number is wrong."

### 2:45 – 3:00 · Back to the board

*Screen: the AO board again, on the terminated sessions.*

> "Rule six of my own linter is 'no visible failure' — every winner I studied kept one on
> the page. So those four dead sessions stay exactly where they are.
>
> It'd be a poor advertisement to hide them."

---

## Notes

- **Under 3:00.** Judges aren't required to watch past it.
- **The board must be on screen at 0:00 and at 2:45.** That's rule 8, and it's the part
  most entrants will treat as an afterthought.
- Type the commands live — a paste looks staged.
- If a command is slow, cut the wait in the edit; don't sit in silence.
