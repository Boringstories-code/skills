---
title: Checkpoint
name: checkpoint
description: >
  Mid-task context reset: writes a SMALL resume note for the current task, then tells
  the owner to /clear so the next session starts fresh in the smart zone. Use when the
  context gauge hits yellow/red, or the owner says "checkpoint", "save and clear",
  "I'm getting full", "context is fat", "reset but remember", "/checkpoint".
  Lighter than /handoff: one task, not the whole session.
type: skill
created: 2026-06-18
source: claude
tags: [skill, core-tools, session, context, smart-zone]
---

# Checkpoint

The fast "clear, don't compact" companion. The status-line traffic light tells you *when* (yellow = wrap up, red = clear). This skill makes clearing **safe and cheap** so you actually do it instead of letting context rot into the dumb zone.

It is the lightweight sibling of [[handoff]]: `/handoff` captures a whole session for someone else to resume; `/checkpoint` captures just the **one task in flight** so *you* can `/clear` and keep going without losing your place.

## Why this exists

Matt Pocock's rule: prefer **clearing over compacting**. Compaction summarizes the whole muddy session and carries "sediment" forward; a clean clear resets to an identical base every time (the model is the man from *Memento* — give it a clean slate, not a running history). The only reason people don't clear is fear of losing where they were. This skill removes that fear.

## When to invoke

- The context window is past about 40% full (answers start getting worse well before the limit)
- `/checkpoint`, "save and clear", "reset but remember", "I'm getting full"
- You're mid-task and the session is getting heavy, but the task isn't done

## What it does

1. **Writes a compact resume note** to `Inbox/handoffs/checkpoint-<slug>-YYYY-MM-DD.md` — short, one task, not a full session dump:
   - **Task** — the one sentence of what you're doing
   - **State** — where you are right now (which step / file / decision)
   - **Done so far** — concrete, terse
   - **Next step** — the single next action on resume
   - **Files in play** — path + why
   - **Don't-lose-these** — any non-obvious facts, IDs, paths, or decisions from this session that aren't written in the code yet
2. **Names your blockers** — any action item only you can do (a decision, a send, a purchase, a value only you have) goes at the top of the note under `## Waiting on me`, so it can't hide in the middle.
3. **Prints a copy-pasteable resume prompt** — one fenced block that points the fresh session at the checkpoint file and the next step.
4. **Tells the owner explicitly to run `/clear`** (the skill cannot clear for them — that is a user action), then paste the resume prompt into the clean session.

## Output shape

```
✅ Checkpoint saved → Inbox/handoffs/checkpoint-<slug>-YYYY-MM-DD.md

Now: /clear   ← do this, then paste the block below into the fresh session

┌─ resume prompt ─────────────────────────────
Resume <task>. State is in Inbox/handoffs/checkpoint-<slug>-YYYY-MM-DD.md.
Next step: <single next action>. Read that file first, then continue.
└─────────────────────────────────────────────
```

## Principles

- **Small.** One task. If it needs the whole session, that's `/handoff`, not this.
- **Distill, don't transcribe.** Paths and decisions, not narration.
- **Forward-looking.** Write it for the version of you that just cleared.
- **Honest.** If something's unverified or half-done, say so.
- Don't pad. The point is speed.

## Files

- Output folder: `Inbox/handoffs/`
- Pairs with: [[handoff]] (the full-session version) and [[session-close]] (end of day).
