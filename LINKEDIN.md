# LinkedIn / X post

Rule 10: *"Public posts on X / LinkedIn are encouraged. Engagement may be considered as a
metric."* Post it **before** submitting, and put the link in the Devpost field.

---

## LinkedIn

```
Yesterday I found out my hackathon submission didn't place.

I spent the evening reading the three winning writeups next to my own. The gap wasn't
engineering — it was four things I could have caught in ten minutes:

→ I never stated a test count. Two winners led with "358 executable assertions" and
  "485 tests."

→ My best number — a sealed image cut 34× down, metadata destroyed, still matched to
  the exact run that made it — was item 3 of a sub-list. The grand prize winner's
  equivalent was their first line, with a job ID and a live URL: "check it yourself."

→ I named my audience once, in "What's next." The criterion literally asked "is there a
  clear audience?" and I postponed the answer.

→ I found three real bugs in the sponsor's SDK and wrote them under "Challenges we ran
  into." The winner filed three pull requests with reproductions and failing tests — and
  led with that.

Same discoveries. Opposite disposition.

So today, in a 2.5-hour hackathon window, I turned those lessons into a linter.

submission-check reads a draft submission and flags what will cost you placement — each
finding quoting the exact span that triggered it, and naming the hackathon the rule was
learned in.

The demo is the part I like: it runs on my own losing submission and finds every mistake
that lost it. Then the same tool on the entry that beat me — and it comes back nearly
silent.

Zero dependencies. No API key. No model in the loop, on purpose: a model would make the
findings unverifiable, and unverifiable findings are the exact problem it exists to fix.

Built with Agent Orchestrator for The Orchestra hackathon — two agents in parallel git
worktrees. Four earlier sessions died on environment friction and I left them visible on
the board, because rule 6 of my own linter is "no visible failure."

Losing taught me more than the two placements did. This is what I did with it.

github.com/Shivang-creator/submission-check

#buildinpublic #hackathon #AgentOrchestrator
```

---

## X (shorter)

```
My hackathon submission lost yesterday.

The build was competitive. The writeup wasn't — no test count, best number buried at item
3, audience deferred to "What's next," SDK bugs filed as complaints instead of PRs.

So I built the linter that catches all four.

It runs on my own losing entry and finds every mistake. Then on the entry that won — and
goes quiet.

Zero deps, no API key, no model in the loop.

Built with @aoagents in a 2.5h window 🕷️

github.com/Shivang-creator/submission-check
```
