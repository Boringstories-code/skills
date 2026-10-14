---
name: session-close
description: |
  End-of-session close-out capturing learnings + the right handoff: captures durable
  learnings, then saves session state. Fires on "wrap up", "wrap this up", "close the session",
  "session close", "/session-close", "let's close out", "I'm done for now", "save my progress",
  "end session", "I need to stop", "pause this session". End of a full session only;
  mid-session one-task reset → /checkpoint.
trigger_phrases:
  - /session-close
  - session close
  - close the session
  - wrap up the session
  - wrap this up
  - I'm done for now
  - end session
  - close out
  - save my progress
  - pause this session
  - I need to stop
  - let's wrap
---

# /session-close — End-of-Session Chain

> **User-invoked skills.** Some skills this one hands off to (`grill-with-docs`, `to-spec`,
> `to-tickets`, `implement`, `implement-spec`, `wayfinder`, `setup-matt-pocock-skills`, `handoff`)
> are marked user-invoked, so the Skill tool may refuse to start them. If it does, Read
> `Skills/<name>/SKILL.md` and follow it inline, in this session. Never skip the step.

One command. Captures learnings, saves state, tells you exactly how to resume.

## Steps (always in this order)

### Step 1 — Distill learnings
Scan this session for anything durable worth keeping:
- New guidance or corrections the owner gave
- Decisions made (with the reasoning)
- Patterns that worked or failed
- Anything that would have saved time if known at session start

If something worth saving exists, show it in chat as a short list and ask which to keep. Each kept one is
appended to the matching file in `00-OS/learnings/` (one file per recurring job or skill, `## Standing
guidance`). A correction about you or how you work goes to `AGENTS.md` instead. Nothing durable? Say so
in one line and skip it.

### Step 2 — Count open threads
Ask the owner: "How many tasks are still open — one, or multiple?"

- **One or more open tasks** → run `/handoff` (one handoff covers every open thread in this session)
- **Nothing open** → skip handoff, confirm the session is clean

### Step 3 — Confirm and sign off
Report in two lines:
- What was saved (proposal file name if any, handoff file name)
- The resume prompt or next step (copy-paste ready)

Keep it brief — this is a close, not a recap.

## When to use /checkpoint instead
`/checkpoint` is for mid-session resets when the context window is getting full — it saves ONE task and tells you to `/clear`. Use `/session-close` at true session end when you're stepping away entirely, not just resetting context.

