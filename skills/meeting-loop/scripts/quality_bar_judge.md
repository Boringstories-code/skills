---
title: Quality bar judge
type: reference
created: 2026-10-08
source: meeting-loop ticket 11
tags: [meeting-loop, private-mode, quality-bar]
---

# Quality bar judge

The prompt for the independent judge whose verdict file gates Private mode
(`quality_bar.py --judged`). Run it with a strong model that did not write the Agent items,
once per RAM path, after `quality_bar.py SITTING_DIR ...` has written each sitting's
`private-items.json` (copy them to `private-items.<run>.json` first: the next run overwrites them).
Internal: not in `release.json`, so it never ships.

## Prompt

You are an independent judge for a release quality gate. Be strict and fair; do not be generous
to either side.

Folder: `<quality-bar folder>`. Sittings: `<list>`. In each:
- `agent-items.json`: the reference action items. Use its `action_items` list.
- `private-items.<run>.json`: the candidate list (a small local model). Each has task, quote, and
  `at` (0-based line index into the sitting's transcript lines).
- The transcript file(s), joined in filename order with timestamps removed. Read them where you
  need context to decide whether two items are the same to-do. Open nothing outside this folder.

Ignore any Agent item whose quote is not found in the transcript (whitespace-collapsed,
case-insensitive): it doesn't count.

For each counted Agent item decide CAUGHT or MISSED:
- CAUGHT = at least one Private item that a person reading the Private list would recognize as
  the same to-do (same action, same object; wording may differ; a broader Private item counts
  only if it would clearly remind the reader of this specific to-do). Each Private item may be
  credited to at most two Agent items, and only when the two Agent items really are one to-do
  split in two. Being near the same transcript line is NOT enough: the Private task text must
  name the same to-do.
- MISSED otherwise.

Classify every Private item as one of: MATCH (credited to an Agent item), REAL-EXTRA (a genuine
to-do the Agent list lacks), DUPLICATE (same to-do as another Private item), NOISE (not a to-do:
explanation, demo narration, done during the call, opinion, past event, vague fragment).

Write verdicts to `judge-<run>.json` as:
`{"<sitting>": {"agent_counted": N, "caught": N, "private_total": N, "match": N, "real_extra": N, "duplicate": N, "noise": N, "misses": ["agent task", ...]}, ...}`

Reply with only: per sitting `caught/agent_counted` and `match/real_extra/duplicate/noise of
private_total`; overall caught/counted; the most common kind of noise; how task wording reads.

## Runs so far

| Date | Run | Judged catch | Noise | Verdict |
|---|---|---|---|---|
| 2026-10-07 | 16 GB, Qwen3-8B, 4 sittings | 61/81 = 75% | 48% | BETA |
| 2026-10-07 | 8 GB, Qwen3-4B, 4 sittings | 58/81 = 72% | 60% | BETA |
