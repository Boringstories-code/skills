---
name: explore-options
description: >-
  The brainstorm step — diverge into genuinely distinct approaches, pressure-test each, and
  converge on ONE with a recorded why-not. Use at the front of the flow, before
  /grill-with-docs, when the best approach isn't obvious. Triggers on 'brainstorm', 'let's
  brainstorm', 'help me brainstorm', 'brainstorm some ideas/options/approaches', 'explore
  options', '/explore-options', 'what are our options for', 'weigh the approaches', 'which way
  should we build this', 'diverge before we commit'.
---

# Explore Options

> **User-invoked skills.** Some skills this one hands off to (`grill-with-docs`, `to-spec`,
> `to-tickets`, `implement`, `implement-spec`, `wayfinder`, `setup-matt-pocock-skills`, `handoff`)
> are marked user-invoked, so the Skill tool may refuse to start them. If it does, Read
> `Skills/<name>/SKILL.md` and follow it inline, in this session. Never skip the step.

The front-of-flow step that opens the space **before** `/grill-with-docs` closes it down.

Grilling is convergent — it sharpens an idea you already hold. Reach here first when you're holding an *itch*, not an idea, and grilling now would just sharpen the first approach that came to mind instead of the best one. This skill diverges, pressure-tests, and converges to one direction — then hands that direction to `/grill-with-docs` to sharpen into a spec.

It produces **decisions, not deliverables** — a chosen direction and a recorded why-not, never code.

## Facts vs. decisions

The same split `/grilling` uses. Before anything else, sort what's open into two piles:

- **Facts** — answerable by looking. Explore the codebase, read the docs, run `/research`. Do not ask the human what you can find yourself.
- **Decisions** — genuine forks with no single right answer. These are what this skill exists to open up and then put to the human. Never answer a decision on the human's behalf.

If sorting reveals there are no real decisions — the approach is forced by the facts — **stop and say so**: skip straight to `/grill-with-docs`. Don't manufacture a fork that isn't there.

## The loop

### 1. Frame

State the goal in one line and the hard constraints — what MUST be true for any approach to count (budget, stack, deadline, a non-negotiable requirement). If the goal itself is fuzzy, name that as the first thing to resolve. A frame is done when you could tell a stranger what "good" looks like.

### 2. Diverge

Generate **at least 3 genuinely distinct approaches** — different bets, not variations of one idea. Force spread on purpose:

- Include one **boring / obvious** approach (the default nobody argues for).
- Include one **left-field** approach (the one you'd dismiss too fast).

For each: the **core bet** (what it's wagering on), what it **optimizes for**, and what it **sacrifices**. If your three options are the same shape wearing different hats, you haven't diverged — go again.

### 3. Pressure-test

Roast each option against the frame. For every approach, name:

- Its **failure mode** — the specific way this one breaks, not a generic risk.
- A **reversible / one-way-door** tag — can you back out cheaply, or does choosing this lock you in? One-way doors raise the bar.
- The **fidelity question** — is there a design question here you can't settle on paper? If yes, this option needs a `/prototype` before you'd trust it (raise the fidelity of the discussion with cheap throwaway code, then come back).

### 4. Converge

Pick **one** direction. Write the decision as:

- **Chosen:** the approach + the one-sentence reason it wins against *this* frame.
- **Why not:** the top one or two runners-up and the specific reason each lost.

The discarded options are not waste — they are the context that makes the choice defensible later. This block **is a proto-ADR**.

### 5. Hand off

Output the proto-ADR and route into **`/grill-with-docs`** to sharpen the chosen direction into a spec (grill records the ADR properly in `GLOSSARY.md`). If the effort turns out too big for one session, route to `/wayfinder` instead. If a prototype is needed first, `/handoff` into a `/prototype` session and come back.

## Output contract

A single short block, nothing else:

```
GOAL: <one line>
CONSTRAINTS: <the hard ones>
OPTIONS CONSIDERED:
  A. <name> — bet / optimizes / sacrifices — failure mode — [reversible|one-way]
  B. ...
  C. ...
DIRECTION CHOSEN: <A/B/C> — <why it wins>
WHY NOT: <runner-up> — <why it lost>
NEXT: /grill-with-docs   (or /prototype first, or /wayfinder if too big)
```

## Anti-patterns

- **Fake divergence** — three variations of one idea. If they share a core bet, they're one option.
- **Anchoring** — quietly deciding on option #1 and staging the rest to lose. Pressure-test honestly or don't run this at all.
- **Skipping the why-not** — the discarded options are the deliverable's value. No why-not, no proto-ADR.
- **Deciding facts** — answering a lookup as if it were a judgment call. Explore first; only forks go to the human.
- **Manufacturing a fork** — running this when the approach is already obvious. Say "no real decision here" and go straight to grill.
- **Producing anything buildable** — this step decides direction. Code belongs to `/prototype` (throwaway) or `/implement` (real).

## Refusal gates

- Refuse to converge on **fewer than 3 genuinely distinct** options.
- Refuse to skip the **why-not** on the discarded approaches.
- Refuse to run when there is **no real decision** to make — route to `/grill-with-docs` instead.
- Refuse to **decide on the human's behalf** — surface each fork and wait.

## When to skip

Skip when the approach is forced or obvious (a one-line bug fix, a well-worn pattern, a decision already made). Skip when the work is too big to hold in one session — that's `/wayfinder`, which does its own decision-mapping on the tracker. This step is for the single-session fork in the road.
