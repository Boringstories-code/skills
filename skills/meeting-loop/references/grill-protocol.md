# Grill protocol (portable copy)

Adapted from the `grilling` skill in mattpocock/skills (github.com/mattpocock/skills; MIT,
© 2026 Matt Pocock; license and credit in the repo's THIRD-PARTY-NOTICES.md), so a receiving agent
with **no skill system** — Grok, Codex, anyone's stock Claude — still runs the same interview.

## Full protocol (what `/grilling` does)

Interview the owner relentlessly until you reach a shared understanding. Map the work as a **design
tree**: every decision branches into the decisions that hang off it.

Work the tree in **rounds**. The **frontier** is every decision whose prerequisites are already settled:
the questions you can ask *now* without guessing at answers you haven't heard yet. Ask the whole frontier
in one round: number each question and give your recommended answer. Then wait for the answers before the
next round.

Format a round like so:

```
❓ **Q1** - **<question title>**: <question body, may be several paragraphs, may list choices>

➡️ <your recommended answer>

---

❓ **Q2** - **<question title>**: <question body>

➡️ <your recommended answer>
```

Each round the answers reshape the tree: settled decisions push the frontier outward and unblock questions
that depended on them. Recompute the frontier and ask the next round. A question whose answer depends on
another question still open in this round belongs to a *later* round, not this one.

Finding **facts** is the agent's job, never the owner's. When a frontier question needs a fact from the
environment (filesystem, tools, the web), look it up — dispatch a worker if it's heavy; don't block on it.
The **decisions** are the owner's: put each to them and wait.

Done when the frontier is empty: every branch visited, nothing left silently assumed. Do not act until the
owner confirms the shared understanding.

## How the handoff seeds it

`ai-handoff.json` → `grill.questions[]` is round 1. Each question carries the item ids it `blocks`. The
receiving agent adds anything it finds while reading the items, runs the rounds, then starts Wave 1.

## Wave execution (the same frontier idea, applied to doing)

Waves are computed by the script from `depends_on` (topological levels). Wave 1 is every item with no
unmet dependency — the execution frontier. Run a wave's items in parallel (one worker each), finish the
wave, move to the next. A wave holding a one-way-door item (send, deploy, publish, pay, delete) pauses for
the owner's explicit confirm before that item, even after the grill. The receiving agent may re-order if
it learns something in the grill; the plan is a starting point, not a cage.
