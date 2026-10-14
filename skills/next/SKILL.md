---
name: next
description: >
  One call for Session B of the build flow: find the next ready ticket, run
  /implement on it (which drives /tdd and /code-review itself), mark it done,
  report the remaining frontier. Fires on "/next", "next ticket", "work the
  next ticket", "keep going on the build", "pick up where the build left off".
  One ticket per fresh session; ends by telling the owner to /clear.
argument-hint: "[ticket number or slug]"
---

# /next — Session B in one call

> **User-invoked skills.** Some skills this one hands off to (`grill-with-docs`, `to-spec`,
> `to-tickets`, `implement`, `implement-spec`, `wayfinder`, `setup-matt-pocock-skills`, `handoff`)
> are marked user-invoked, so the Skill tool may refuse to start them. If it does, Read
> `Skills/<name>/SKILL.md` and follow it inline, in this session. Never skip the step.

Conductor, not craft. Keep `ponytail` on for code shape.

## 1. Find the frontier

Read `docs/agents/issue-tracker.md` to learn the tracker.

- **Local markdown:** list `.scratch/*/issues/*.md`. A ticket is **open** when
  its `**Status:**` line is `ready-for-agent`. A ticket is **ready** when open
  and every ticket named in its `**Blocked by:**` line has `**Status:** done`
  (or the line says "None"). Frontier = ready tickets, lowest number first.
- **GitHub / Linear:** ready = label `ready-for-agent`, open, no open blocking
  issue. Use `gh issue list --label ready-for-agent --state open` (or the
  tracker's equivalent) and check blockers.

Argument is a ticket number → use that ticket, but refuse if it's still
blocked (say what blocks it). Argument is a feature slug → first frontier
ticket inside that feature. No argument and only one feature has open tickets
→ take its first frontier ticket. No argument and several features are open →
ask which feature (one question, list them), then go.

Nothing open at all → go to step 4 (Close out).

## 2. Implement

Run `implement` with the ticket as its input. It drives `tdd` at the agreed
seams, typechecks, runs tests, runs `code-review`, commits. Do not call
`tdd` or `code-review` yourself. Do not start a second ticket in this window.

## 3. Mark done

- Local: set `**Status:** done` and tick the acceptance boxes that passed.
  Leave unticked boxes unticked and say so.
- GitHub / Linear: close the issue with a one-line comment naming the commit.

## 4. Report, then stop

```
Ticket done: NN-<slug>  (commit <sha>)
Remaining: <N> open  |  Frontier: <NN, NN>  |  Blocked: <NN>

Next: /clear, then /next
```

Two or more tickets already done and the frontier has 2+ ready? Add one line:
`Shape is set: /implement-spec can run the rest in parallel while you stay nearby.`

**Close out** when no tickets remain:

```
All tickets done for <feature-slug>.
Next: open a PR if this lives on a branch, then /code-review the whole feature once.
```

## Refusals

- Ticket's acceptance criteria don't pass and code-review flagged it → do
  not mark done. Report the failing criterion and stop.
- Context is already fat before step 2 → stop and say `/clear` first; a
  ticket deserves a fresh window.
