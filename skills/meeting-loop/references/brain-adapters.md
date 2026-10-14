# Brain adapters — writing into someone else's knowledge architecture

Meeting Loop produces the same six artifacts every run. Where they land, in what form, at what
granularity, and how they merge with what's already there is entirely a property of the user's brain —
Obsidian vault, Logseq graph, a `docs/` folder in a repo, Notion, a `.brain/` project wiki, or a bare
folder with no system at all.

This file is the contract. `profile.brain` picks an adapter; the loop reads the adapter and stops
guessing.

## The six artifacts

| id | What | Sensitivity |
|---|---|---|
| `transcript` | cleaned, speaker-attributed | often sensitive |
| `raw` | ASR json/txt/segments + source audio pointer | always treat as sensitive |
| `action_items` | the mode's `output_shape` doc | usually shareable |
| `entity_note` | living per-entity note (client / project / band / account) | shareable |
| `person_note` | Channel B private dossier | never leaves the private root |
| `concepts` | reusable atomic knowledge distilled outward | shareable, cleaned only |

## The five questions an adapter must answer

1. **Where** — `folder_map`, artifact id → path under `root`.
2. **Form** — `link_dialect` + `frontmatter`. Markdown with `[[wikilinks]]` is not the same substrate as
   markdown with `[text](path)`, and neither is a Notion block.
3. **Granularity** — one note per meeting, atomic concept pages, append to a running doc, or DB rows.
4. **Merge policy** — how a living note absorbs a new meeting without duplicating or clobbering.
5. **Capability** — `direct-write` (we have the filesystem) or `handoff` (we emit files and something
   else imports them). **Never claim a write you cannot make.** A handoff adapter reports the file it
   produced and the import step; it does not say "added to Notion."

## Merge strategies (the vocabulary)

The loop knows four. An adapter picks one per artifact; the synthesizer agents are told which.

- **`append-dated-block`** — new `## 2026-08-23 — <topic>` section at the end. Never edits prior text.
  Safest. Default for entity notes and person notes.
- **`rewrite-section`** — replace a named section (e.g. `## Current scope`) and emit a
  ```changes``` block naming what moved. Requires stable headings. Use only where the note has a
  known shape.
- **`new-note-and-link`** — write a fresh dated note, add one backlink line to the hub/MOC/index.
  Default for meeting notes in link-capable brains.
- **`upsert`** — keyed row write for DB-shaped destinations (task tracker, CRM, Notion database).
  Requires a stable key; without one, insert-only and say so.

**Never-overwrite is absolute.** Every strategy above either appends, replaces a section it can name, or
creates a new file. Nothing truncates an existing file. If a target exists and the strategy can't apply
cleanly, write beside it with a `-2` suffix and report the collision.

## Distillation tiers

"Distill" means different things depending on how much brain there is to distill into. Pick per install
(`profile.distillation.level`), not per meeting.

**L0 — capture only.** Transcript + action items. No knowledge extraction, no entity notes, no wiki.
Correct for: a bare folder, a first-week install, a privacy-heavy context, or anyone who just wants the
to-dos. Default for `adapter: none`.

**L1 — entity notes.** Plus a living note per client / project / person / account, merged with
`append-dated-block`. This is where most installs should sit. Requires the brain to have a stable
concept of an entity — a folder per client, a page per account. Cheap, high value, low risk.

**L2 — atomic concepts.** Plus reusable knowledge wicked out of the meeting into the brain's own
concept layer as densely-linked atomic pages. Requires `link_dialect != none` AND an existing wiki AND
a distillation engine (`second-brain-ingest` for a vault, `project-brain` for a repo). Without all
three, L2 silently degrades to L1 — say so rather than inventing a wiki the user didn't ask for.

### Distillation rules (all tiers)

1. **Distill cleaned artifacts only.** Raw ASR and raw audio never reach the brain. A hallucinated ASR
   line promoted to an atomic "fact" is permanent and untraceable.
2. **One concept per page; merge before you create.** Search the existing concept layer first. A second
   page on the same idea is worse than no page.
3. **Cite back.** Every distilled claim carries a link to the meeting note it came from, so a wrong
   claim can be traced to the sentence that produced it.
4. **Private channels never distill outward.** Person dossiers and identity/belief lines stay in the
   private root. They may shape tone; they never supply content.
6. **Respect the house style.** If `brain.conventions_doc` exists (a `CLAUDE.md`, README, or style
   guide), read it at Step 0 and match its filename rules, frontmatter keys, tag budget, and heading
   conventions. Do not impose ours on someone else's system.

## Shipped adapters

### `obsidian`
- form: markdown + `[[wikilinks]]` + frontmatter. granularity: `note-per-meeting`, L2 capable.
- merge: `new-note-and-link` for meetings, `append-dated-block` for entity/person notes.
- conventions to detect: kebab vs Title Case filenames, whether dates appear in filenames (they break
  wikilinks in some vaults — check before adding one), MOC/hub backlink habit, tag budget.
- gotcha: a vault is usually synced. Assume `destination_shared: true` until proven otherwise.

### `logseq`
- form: markdown, block-level bullets, `[[page refs]]`, journals. granularity: `append-to-running-doc`
  (today's journal) + page refs out to entities.
- merge: `append-dated-block` into the journal; entity pages accumulate linked refs automatically.
- gotcha: outline-first. A wall of prose in a Logseq page is a foreign object — write bullets.

### `plain-folders`
- form: markdown, no links (or relative `[text](path)`), dated filenames, no index.
- granularity: `note-per-meeting`. Distillation: **L0 or L1 only.**
- merge: `new-note-and-link` degrades to `new-note`; optionally maintain a simple `INDEX.md`.
- **This is the correct default when in doubt.** It works everywhere, breaks nothing, and can be
  upgraded later once the user has an actual system.

### `project-brain`
- form: the repo's `.brain/wiki/`. granularity: `atomic-pages`. L2 native.
- meeting-loop's job shrinks: drop the cleaned transcript into the brain's raw intake and call the
  `project-brain` ingest. Do not hand-write wiki pages — that skill owns page shape and dedup.
- merge: `upsert` by concept, handled downstream.
- fit: dev/build meetings on a repo that already has a brain.

### `git-repo-docs`
- form: markdown + relative links under `docs/`. granularity: `note-per-meeting`.
- **merge: propose a branch + PR, never commit to the default branch.** A meeting note is not worth a
  direct push to main.
- gotcha: the repo is shared by definition. Sensitive transcripts must route to the private root, and
  raw audio must never enter git.

### `notion`
- capability: **`handoff`**. Blocks, not files; action items belong in a database, not a page.
- produce: one markdown file per artifact plus a JSON payload shaped for import. Report the file paths
  and the import step. If a Notion MCP/API is connected and authorized, an upsert may run — but say
  which rows were written, and never silently.
- merge: `upsert` keyed on a stable page/row id; without one, insert-only.

### `none`
- No brain. Everything lands in one dated folder next to the audio. Distillation `L0`, hard.
- Say plainly: "no knowledge layer configured — you're getting a transcript and a to-do list." Then
  offer to set one up later. Do not fabricate a folder hierarchy the user never asked for.

## Adding an adapter

Adapters are data plus a strategy choice, not code. To add one: give it the five answers, map each of
the six artifacts to a folder and a merge strategy, declare the distillation ceiling, and note the one
gotcha that will bite. If a new brain can't be expressed in the four merge strategies, that is the
signal to add a fifth strategy to this file — not to special-case it inside the loop.
