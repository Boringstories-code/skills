---
name: person-enrich
description: >
  Capture and enrich what the owner knows about a PERSON into their private dossier under
  `People/`. Fire whenever the owner describes, mentions, or dumps context about a human —
  "remember about <name>", "here's what I know about <name>", "enrich <name>",
  "add this to <name>'s note", "/person", "/enrich-person", or just talking about who
  someone is, what they do, their family, how they are. STRICTLY PRIVATE (Layer 1):
  People/ never crosses into client-facing work, the wiki, or any shared team tool.
---

# person-enrich

Turn anything the owner knows about a human into durable understanding in `People/`. The longer it runs, the
richer the map of the people in their world — so when they ask "how do I approach Dana on X," the answer
comes from who Dana actually is.

**Go as deep as the material allows — always.** the owner's standing rule: enrich every person as fully as
possible, capture every real signal, and leave the note knowing more about them than before. Depth is the
point, not brevity. Never thin out what's there.

See `People/_DESIGN.md` for the full model and `People/_TEMPLATE.md` for the note skeleton.

## Privacy — non-negotiable (Layer 1)
`People/` is private: the owner's own devices only. NEVER ingest it into the wiki, NEVER sync it
to any shared team tool, NEVER reproduce its contents in any client-facing artifact. Private context may shape the
*tone* of client work (go gentle, don't rush) but the facts NEVER appear on the page. **Four tiers,
graduated by audience:** the note body is **Layer 1 (private — the owner only)**; the two blocks at the bottom
are **Layer 2 (Business / working read — for people working with them, and client/business work)** and
**Layer 3 (Safe-to-share — anyone)**. Only Layers 2 and 3 may cross the wall; Layer 1 never leaves.
**Level 0 — the inner circle** (a partner + the owner's own truly-private material) sits below Layer 1 in
`People/_level-0/` (`privacy: level-0`): NO Layer-2/3 blocks, nothing shareable ever, capture-only — enrich
it only when the owner explicitly asks and never surface it elsewhere.

## When to fire
- the owner explicitly asks to remember/enrich a person, or types `/person` · `/enrich-person`.
- **Auto, no gate:** the owner describes a human in normal conversation (who they are, what they do, their
  family, a story about them). Fold it in quietly. Only a genuinely new human gets a soft "started a note
  for <name> — here's what I caught," never a blocking prompt.

## How to enrich

1. **Resolve the person.** Check `People/_names.md` (the canonical name map) FIRST — it resolves known
   transcript mis-hears and lists the look-alike names that are *not* the same person. Then match the name
   against `title` + `aliases` across `People/*.md`. One match → that
   note. No match → new note from `People/_TEMPLATE.md`, filename = stable kebab-case (the wikilink anchor,
   set once, never renamed); seed `aliases` with every name the owner uses for them. Never fork a second note
   for one human.
   **Name them fully.** Always chase first AND last name. Surname unknown or only
   half-heard on a single-mic tape → title the note **first name + where they're from** (`Odette (book club)`),
   put the heard surname in `aliases` marked unconfirmed, and file an `_asks.md` question for the owner to
   confirm with the person directly. Never guess a spelling; never leave a bare first name with no origin.
2. **Route the content** into the right sections — Who they are, What drives them, How I know them, Life,
   Household & family, Work, How to be with them, Stories & anecdotes. Only fill where there's real signal;
   empty sections stay as prompts.
3. **Stamp a dated thread.** Prepend to `## Threads`: `- <YYYY-MM-DD> — <what was learned>`.
3b. **Promote durable insight up — the log is not the finish line.** The Threads entry records *what
   happened on a date*. After stamping it, lift any **lasting, identity-level** insight (a trait, a driver, a
   way to be with them, a work fact) up into the standing sections so the note reads as a current dossier,
   not a timeline you have to mine. Rule of thumb: a one-time event stays in Threads; anything that's now
   *true about who they are* belongs in Who they are / What drives them / How to be with them / Work. Merge
   into existing prose; don't duplicate.
4. **Link the graph.** Every other human mentioned → `[[wikilink]]`, stubbing unknowns (a dimmed link
   surfaces who to capture next). Family, partners, who they trust, who introduced them. Density is the
   product — connections are the intelligence.
5. **Keep BOTH bottom blocks current — REQUIRED for every person:**
   - **Layer 2 — Business / working read.** How they OPERATE in a work/business context: role, decision
     authority, how they decide, communication style, what they value in the work, the working
     relationship, real business knowledge about them. The read used in client/business work or shared
     with a collaborator. Can be candidly operational ("decides slow, needs the why first"). If they're not
     a business contact, give the working-relationship read instead.
   - **Layer 3 — Safe-to-share (anyone).** The surface read fine to say to literally anyone: name,
     role/title, how you know them, general vibe. Nothing sensitive even at this level.
   NEVER put personal/health/family/faith/mental-health detail in either block — that stays Layer 1. If
   almost nothing is safe at a layer, say so explicitly rather than leaving it blank.
6. **Merge, never lose.** Add to prior knowledge; contradictions → keep both and note the change with a date.

## Querying a person (the payoff)
When the owner asks how to approach someone, read their note PLUS the graph around them (who influences them)
PLUS recent Threads, weighting recent over old. Flag staleness ("your last real read on <name> is N months
old") rather than answering from a frozen snapshot. This is a private, owner-only read.

## Out of scope
The client engagement (decision authority, scope, deal) lives in the client folder / `client-profile.md`,
not here. This skill is about the human.

> Hit a contradiction, an unplaceable person, or a promotable edge while
> enriching? Don't guess — append a question block to `People/_asks.md`
> (format: "Asks protocol" in `People/_DESIGN.md`).
