---
name: build
description: >
  One call for Session A of the build flow: idea → grill → spec → tickets →
  checkpoint, in one unbroken context window. Wraps the vendored Matt Pocock
  spine (grill-with-docs, to-spec, to-tickets) without editing it. Fires on
  "/build <idea>", "build this", "start a build", "plan and ticket this",
  "let's build <thing>", "spine this". Not for one-liners or quick fixes.
argument-hint: "<idea, brief, or spec path> [--explore] [--wayfinder]"
---

# /build — Session A in one call

> **User-invoked skills.** Some skills this one hands off to (`grill-with-docs`, `to-spec`,
> `to-tickets`, `implement`, `implement-spec`, `wayfinder`, `setup-matt-pocock-skills`, `handoff`)
> are marked user-invoked, so the Skill tool may refuse to start them. If it does, Read
> `Skills/<name>/SKILL.md` and follow it inline, in this session. Never skip the step.

You are the conductor, not the craft. Each step below is a skill; run it with
the Skill tool, let it finish, then move on. Never skip a step, never answer a
grill question on the owner's behalf, never write code here. Run `ponytail` once
at the start so the plan stays small.

## Preflight (silent, fix or stop)

1. `docs/agents/issue-tracker.md` missing → run `setup-matt-pocock-skills`
   first. It asks tracker (GitHub / local) and label vocab. Then continue.
2. Context already fat (past ~40% of the window)? Stop: tell the owner to
   `/checkpoint` then `/clear` and re-run `/build` fresh. Steps 3–5 must share
   one clean window.

## Steps

3. **Diverge — only when needed.** Run `explore-options` if `--explore` was
   passed, or if the approach is genuinely open (two or more real ways to
   build it). Skip when the owner already knows the shape. Effort is fog-sized
   (`--wayfinder`, or "I don't even know where to start")? Run `wayfinder`
   instead; it hands off to `to-spec` itself.
4. **Grill.** Run `grill-with-docs`. Ask the owner the questions one batch at a
   time. Do not stop grilling early to seem fast; do stop when the plan holds.
   It writes ADRs and updates `GLOSSARY.md`.
5. **Spec.** Run `to-spec`. Pure synthesis of the conversation. Confirm the
   spec landed on the tracker with `ready-for-agent`.
6. **Tickets.** Run `to-tickets`. Vertical slices, dependency-ordered, each
   sized for one fresh window. Local tracker → `.scratch/<feature-slug>/issues/NN-<slug>.md`.
7. **Checkpoint.** Run `checkpoint` so the resume note exists.

## Close

Print exactly this shape, then stop:

```
Build planned: <feature-slug>
Spec: <where>
Tickets: <N> (<list of NN-slug>)
Frontier (no blockers): <NN, NN>
Code: <the **Code:** line>

Next: /clear, then pick how to run the tickets:
  /next                    watch each one (do this for the first 2-3, while the shape is set)
  /implement-spec          you're nearby, no Docker: parallel subagents, one PR
```

Before printing, make sure the spec carries one `**Code:**` line listing every
folder the tickets and their tests touch (`~/code/<repo>`, or vault folders,
comma-separated, folders not files).

## Refusals

- No tracker configured and the owner declines setup → stop; the spine can't
  publish without one.
- the owner asks to "just build it" mid-grill → remind once that skipping the
  grill is the #1 cause of the wrong thing getting built; if he reaffirms,
  jump to step 5 with what's known and mark the spec `assumptions:` clearly.
