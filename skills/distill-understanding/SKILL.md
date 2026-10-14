---
name: distill-understanding
argument-hint: <source-path> | brief | stage
description: The understanding layer above every distiller. Turns any distilled source — meeting transcript, video note, email/text thread, article, wiki source — into typed CONCEPT CARDS (claim · mechanism · evidence · typed edges · open questions · so-what) under 00-OS/wiki/concepts/, and runs the weekly connector brief that finds convergence, contradiction, and gaps across the whole corpus. Use on '/distill-understanding', 'what did I learn from this', 'extract the concepts', 'distill this for understanding', 'connect this to what I know', 'learn from this video', 'learn from this transcript', 'run the understanding brief', or after meeting-loop / second-brain-ingest. Write-isolated to 00-OS/wiki/concepts/. Slash is /distill-understanding.
---

# /distill-understanding

**Why this exists:** to learn like a human does — key concepts, and how they connect. Every other
distiller extracts *items*: [[meeting-loop]] → actions, [[second-brain-ingest]] → entities/claims.
Wiki links are untyped ("related"); understanding is typed ("causes", "contradicts"). This skill is
the card layer on top.

Three modes. Default is `extract`.

## Runtime (Claude and Grok)

Judgment work. A fast model produces bullet soup.

| Runtime | Extract / brief |
|---|---|
| **Claude** | Dispatch `concept-extractor` on `opus`. |
| **Grok** | Follow `agents/concept-extractor.md` on the **session model** (`grok-4.6`). Optional: spawn `general-purpose` pinned `model: grok-4.6` to keep the main thread lean. **Do not spawn `opus`** (Grok cannot). **Do not drop to `grok-4.5` or grok-build.** |


## Mode: extract  —  `/distill-understanding <source-path> [--source-slug S] [--date D] [--unattended]`

Input: any text file — a cleaned transcript, `00-OS/wiki/creators/<c>/<video>.md`, a
`00-OS/wiki/<domain>/_sources/<slug>.md`, a staged message under `00-OS/raw/messages/`, or any
`.md` under `00-OS/raw/`. Pasted text with no file → run `stage` first (below), then extract.

1. Read `references/concept-card.md` and `references/edge-vocabulary.md`. Not optional; the gate
   lives there.
2. Run **`concept-extractor`** (`agents/concept-extractor.md`) per **Runtime** above, with: the source
   path, `source-slug`, `date`, and `People/_names.md` if present. It reads, gates, dedups, writes
   0–4 cards + the `_sources/` summary, lints, updates `_index.md` and `log.md`.
3. Confirm exit 0 from `python3 Skills/distill-understanding/scripts/concepts.py lint <new cards>`.
   Anything failing gets fixed or dropped — a card that can't pass lint isn't understood yet.
4. Report: created / merged / contested / stubs, or `none`. `none` is a normal, honest result.

`--unattended` (headless, from a cron or another skill): ask nothing; put ambiguity in the
`_sources/` page under `## Review needed`; never mint on an unsure dedup.

**Where it runs:**
- [[second-brain-ingest]] → offer it after an ingest when the source taught something.
- After [[meeting-loop]] → offer it on the cleaned transcript.
- A video, article or book you want to **learn from** → run it on the transcript or notes.
- Messages have no distiller of their own → `stage` + extract by hand when a thread
  teaches something.

## Mode: brief  —  `/distill-understanding brief [--since 7]`

The weekly connector pass. Ingest-time extraction can't see across sources; this can. Run it on demand;
weekly is a good rhythm.

1. `python3 Skills/distill-understanding/scripts/concepts.py brief-data --since 7` → the mechanical
   seed: fresh cards, convergence candidates (3+ sources), contested, stale open questions (30d+),
   stubs, one-way edges, orphans.
2. Read every fresh card and every convergence/contested card in full. Then the judgment work,
   per **Runtime** above:
   - **Convergence** — where 3+ sources now agree, say in one paragraph what is now *held* and
     promote `confidence` / `status` on the card (edit the card; note it in the brief).
   - **Contradiction** — for each contested card, frame the live question for the owner in one line
     with both sides cited. Never resolve it for them.
   - **Connections he didn't see** — pairs of cards from *different* `topics` that share a
     mechanism. Propose the edge; write it if it survives the edge-vocabulary test.
   - **Gaps** — stale open questions and stubs: which two are worth an hour this week, and why.
   - **Retire?** — a card contradicted by own-work evidence for 60d+ → propose `retired`.
3. Write `Inbox/understanding/YYYY-MM-DD_brief.md`. Short: 5 sections above, bullets,
   every line cites `[[card]]`. Internal artifact — no humanizer needed, no HTML.
4. Any card edited gets `updated` bumped and re-linted. Append one `log.md` line: `… | brief | …`.

## Mode: stage  —  `/distill-understanding stage --kind <message|email|text|thread|video|note> --slug <s> [--file F]`

The messages lane. Copies a thread, DM, email, or paste into `00-OS/raw/messages/<date>_<slug>.md`
with provenance frontmatter so the extractor has a stable source to cite.
`python3 Skills/distill-understanding/scripts/concepts.py stage --kind email --slug <s> --file <f>`
(or pipe on stdin). Then run `extract` on the printed path. Raw is never edited afterward.

## Hard rules

- **Write only under `00-OS/wiki/concepts/`** (+ one `log.md` line, + the brief in
  `Inbox/understanding/`). Never edit the source, `People/`, `Life/`, other wiki domains.
- **Roles, never names.** People/ firewall applies in full; `lint` blocks names from
  `People/_names.md`. Client-neutral cards; the meeting slug lives in `_sources/` only.
- **Mechanism or it isn't held.** A card whose mechanism restates its claim fails lint. If the
  source never explains, write "source asserts, mechanism unknown" and keep `status: forming`.
- **Contradictions are recorded, never resolved.** Same rule as the wiki.
- **Zero is a valid harvest.** Never pad. A thin card costs more than a missed one — real concepts
  recur across sources; a wrong one gets cited.
- **Cost guard:** one judgment pass per source, 0–4 cards (Claude: opus; Grok: grok-4.6). Never run
  `extract` over a whole back catalog without the owner's explicit go — same rule for any big batch.

## Files

- `references/concept-card.md` — schema, template, the gate, dedup, lifecycle, privacy
- `references/edge-vocabulary.md` — the eight edge types and the test for each
- `agents/concept-extractor.md` — the extractor brief (Claude opus / Grok grok-4.6)
- `scripts/concepts.py` — `lint` · `graph` · `brief-data` · `stage` · `selftest`
