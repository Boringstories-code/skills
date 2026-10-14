# The method — one loop, the voice target as a parameter

**What this file is.** The rewrite loop that `humanizer` and every register skill built on it both
run. It was written twice, in two skills, in two wordings, and the two started to drift. This is the
single statement of the loop; each skill supplies a **parameter block** and nothing else.

**Why it is separate.** Two copies of one method drift apart. A method restated in each consumer diverges silently, and the divergence surfaces as a
skill doing the right thing for the wrong reason — or the wrong thing convincingly.

**What this file is not.** It carries no patterns, no kill list, no voice cards, no scores. Those are
each skill's own. This is the shape of the work, not its content.

---

## The loop

### A. Read the situation before you rewrite

Four questions, always, before touching a word:

- **Who reads this?** One named person, a list, a client, an engineer, a crowd.
- **What medium?** Email, landing page, pitch, script, proposal, internal note, technical doc.
- **What is the job of the text?** Get a reply, sell, explain, reassure, set a date.
- **How much polish is right?** A text to a friend and a legal-facing proposal are not the same
  register.

A register skill adds its own questions here — see its parameter block. A question that can stop the
work belongs in this phase, not later: the cheapest refusal is the one made before the rewrite.

### B. Pick the target, and state it

Name the voice. A register skill also names its setting. **State it in the output**, before rewriting.

An undeclared target is the failure this phase exists to prevent: a rewrite with no named target
drifts toward generic "natural," which is its own tell. Declaring it makes the choice reviewable, and
a reviewer can only argue with a target that was written down.

**Never infer a register.** Sales-shaped copy is not automatically sales-register copy. Applying a
register nobody asked for is the same defect as guessing the voice.

**Where a register and a voice collide, the voice wins.** A register is borrowed; a voice is owned.

### C. Score before you rewrite

Score first, then decide how hard to work. Scoring after rewriting is not scoring — it is
justifying.

The axes are each skill's parameter. What every axis shares:

- **Score clusters, not single habits.** One signal per violated rule per paragraph, plus one for
  document-level density. Never one per occurrence — that lets a single habit push clean copy into a
  rebuild, which is over-correction arriving through arithmetic instead of judgment.
- **A hard block ignores the ladder.** A score in the leave-it band does not license "ship" when a
  blocking defect fired (an invented figure, an untraceable claim, a do-not-say violation). Report
  the block; never let a low total imply the copy is fine.
- **A high score can mean stop, not work harder.** Every ladder needs a top rung that escalates
  instead of rewriting. Copy with nothing underneath it is not a copy problem, and rewriting it
  produces a well-written version of nothing.

### D. Rewrite toward the named target

Toward *that register*, never toward a generic "natural" one. Preserve the core message, match the
target's cadence, and add a real stance or a concrete detail — pattern removal alone leaves clean
text with nobody behind it.

**At the top of the ladder the risk inverts.** Over-correction is the failure mode on near-clean
input; on a full rebuild the danger is the opposite. When the source carries no facts, deliver
*structure* and leave a **named slot** for the specific. A bracketed slot the caller must fill is a
correct output. An invented specific is a defect however well it reads — and it will read well,
which is the whole problem.

**Protect what the caller supplied.** Never re-word a clause containing a figure, name, date, or
URL; rewriting around a number is how a digit moves. And never apply a clever fix to a figure you
were handed a source for — reaching for the better-sounding version of a sourced number is inventing
a problem.

### E. Verify, then gate

Run the skill's done test, then read the result once more as the person it is for, with the target
voice named. That last read is never skipped: every word an outside reader sees gets this pass.

---

## The parameter block

A skill built on this loop declares these and nothing more:

| Slot | What it supplies |
|---|---|
| **Extra situation questions** (A) | Anything that can stop the work before a rewrite starts |
| **Target vocabulary** (B) | What the target is called, and what settings it has |
| **Score axes and ladder** (C) | What is counted, the bands, and the escalation rung |
| **Patterns and kill list** (D) | The catalog the rewrite works against |
| **Done test** (E) | The questions that decide it is finished |

Adding a register means writing a parameter block, not restating the loop. If a new skill needs to
change the loop itself, change it **here** — that is what this file is for.

---

## Consumers

- `Skills/humanizer/SKILL.md` — the base. Voice targets, the 33-pattern catalog, the residue ladder.

