---
name: what-can-i-do
description: >
  Answer 'what can this thing do' — recommend the right skill or command
  for a task. Use on 'what can I do', 'what skills do I have', 'is there something for X', 'do
  I have a tool for this', 'what's available', '/what-can-i-do'. Read and answer only; never
  does the downstream work.
allowed-tools: [Read, Glob, Grep]
---

# What can I do

The router. Someone describes a task; you name the thing that handles it.

## How to answer

1. Read `Skills/SKILL-ATLAS.md`. That's the index. Then list the folders in `Skills/`: a skill
   installed after the brain was set up (the free skills repo, or one you wrote) may not be in the
   atlas yet. For each folder the atlas doesn't name, read the `description` at the top of its
   `SKILL.md`.
2. Check `drawers/` for a topic pack matching the subject. Empty in a fresh vault.
3. Then answer.

Name **one** primary recommendation and at most two alternatives. A list of twelve options is
not an answer — the person asked because they didn't want to choose.

## Shape of the answer

- What to run, exactly as they'd type it.
- One line on what it does.
- One line on what it won't do, if that's a live risk.

## When nothing fits

Say so plainly, then say what the closest thing is and what it would take to make a real one.
"There's no skill for that yet — `capture` will hold it, and if you do this weekly it's worth
writing a skill" is a better answer than stretching an unrelated skill to cover it.

## Don't do the work

This skill recommends. It doesn't execute. If the answer is obvious and the owner clearly
wants it done, say which skill to run and offer — don't silently become that skill.
