---
name: second-brain-ingest
description: Ingest a raw source (or a directory of sources) into the owner's 00-OS Karpathy-style wiki. Reads the source, extracts entities/concepts/claims/sources, and creates or MERGES densely-wikilinked atomic pages under 00-OS/wiki/<domain>/. Use on '/second-brain-ingest', '/ingest', 'ingest this', 'absorb this source', 'process the latest raw'. Write-isolated to 00-OS/wiki/ — never edits raw sources or notes elsewhere.
---

# second-brain-ingest

Implements Andrej Karpathy's LLM-wiki pattern (see `references/karpathy-pattern.md`)
against the owner's `00-OS/` schema (see `00-OS/README.md`). Ingestion is **active
synthesis, not indexing**: read the source, then build/maintain persistent,
interlinked markdown pages.

## When to use

Trigger phrases: `/second-brain-ingest`, `/ingest`, "ingest this", "absorb this
source", "process `<file>`", "ingest the latest raw".

## Input contract

One argument: a path **inside `00-OS/raw/`**, which is either:
- a single file → ingest that file, or
- a directory → ingest every `.md` (and `.txt`/`.vtt`) file in it, one at a time.

Optional flags:
- `--domain <slug>` — force the domain. If omitted, infer from content.
  Domains are the folders under `00-OS/wiki/` plus the sections in `00-OS/wiki/index.md`. Minting a
  new domain needs the owner's explicit ask — never create one silently.
- `--unattended` — overnight mode: skip ALL human-in-the-loop questions, use best
  judgment, and record any ambiguity in a `## Review needed` section of the most
  relevant page (create the section if absent).
- `--dedup-check --domain <d>` — run a dedup pass over an existing domain (no new
  source): find duplicate entity/concept pages, merge them, see `references/dedup-rules.md`.

## Behavioral spec (per source file)

1. **Read the raw file fully.** Never edit it.
2. **Determine the domain** (from `--domain`, else infer): one of the 20 canonical domains listed under the `--domain` flag above (the folder set under `00-OS/wiki/`).
3. **Extract four kinds of things:**
   - **Entities** — proper nouns: gear, brands, clients, people, protocols, products,
     standards, venues, file formats. (e.g. `Notion`, `Roth IRA`, `sourdough starter`, `USB-C`)
   - **Concepts** — ideas, patterns, methodologies, workflows. (e.g. `Named Controls`,
     `Client Acquisition Funnel`, `Gain Staging`)
   - **Claims** — factual assertions worth tracking, especially version-specific or
     contestable ones. These become bullets under Key facts with provenance.
   - **Sources** — URLs/refs cited *inside* the raw file. These go in the page's
     Sources section and the source-summary page.
4. **For each entity → create or MERGE** `00-OS/wiki/<domain>/<slug>.md` using the
   **entity template** in `references/page-templates.md`.
5. **For each concept → create or MERGE** `00-OS/wiki/<domain>/<slug>.md` using the
   **concept template**.
6. **Wikilink aggressively** per vault `CLAUDE.md`: link concept-level terms on first
   mention per page — gear, brands, clients, people, protocols, formats, key projects.
   Use aliases for prose: `[[Named Controls|named controls]]`. Dimmed links to
   not-yet-existing pages are **intentional stubs** that surface knowledge gaps — create
   them freely. Do NOT invent unverifiable file-path links.
7. **Create the source-summary page** `00-OS/wiki/<domain>/_sources/<source-slug>.md`
   using the **source-summary template**. List every page this source created/updated.
8. **Append one line to `00-OS/wiki/log.md`** inside the fenced table:
   `YYYY-MM-DD HH:MM | <source-path> | <N> created | <N> updated | <domain>`
9. **Update `00-OS/wiki/index.md`** — add any new entities/concepts under their domain
   section with a one-line summary.
10. **Update the domain `_index.md`** (`00-OS/wiki/<domain>/_index.md`) — list new
    pages under Entities / Concepts / Patterns / Sources.
11. **Understanding pass.** Run `/distill-understanding <source-path> --source-slug <source-slug>`
    (`Skills/distill-understanding/SKILL.md`; add `--unattended` when this skill is). Entities and
    claims above are *knowledge*; this writes the *understanding* — typed concept cards under
    `00-OS/wiki/concepts/` (claim · mechanism · edges · open questions · so-what). 0–4 cards per
    source, `none` is normal. The `concepts` domain is the one domain this skill writes outside
    `<domain>/`.

## Slugging

`kebab-case`, no dates. `USB-C` → `usb-c.md`. `Roth IRA` → `roth-ira.md`.
Strip articles. Stable names protect wikilinks — reuse an existing slug rather than
minting a near-duplicate (see dedup rules).

## Dedup rules (summary — full rules in `references/dedup-rules.md`)

- **If the target page exists, MERGE — never overwrite.**
- New facts append as bullets tagged with provenance: `- <fact> (YYYY-MM-DD source: <slug>)`.
- Add the new source to the page's `sources:` array; keep `source:` as the first/primary.
- **Conflicting claims** → do NOT pick a side. Record both under a `## Contradictions`
  section with provenance for each, and (in `--unattended`) add a `## Review needed`
  note. This mirrors Karpathy: flag, don't silently resolve.
- A home-folder source and its vault twin (`home--x.md` / `vault--x.md`) MERGE into one
  canonical page with `sources: [home--x, vault--x]`.

## Write-isolation (hard rule)

- **Only write under `00-OS/wiki/`.**
- **Never** modify files in `00-OS/raw/`.
- **Never** modify the owner's pre-existing notes in `Skills/`, `Personal/`, `Notes/`,
  `Projects/`, or anywhere outside `00-OS/wiki/`.
- If following an instruction would require writing outside `00-OS/wiki/`, STOP and flag.

## Modes

- **Interactive**: before ingesting, may ask "Anything specific to extract or skip?"
- **`--unattended` (overnight)**: ask nothing. Use best judgment. Capture every
  ambiguity in a `## Review needed` section of the relevant page so it's reviewable.

## Quality bar (self-check after each source)

- Pages are atomic (one entity/concept each), not dumping grounds.
- Wikilinks present, not raw mentions of linkable terms.
- Every page has the full template frontmatter and all body sections (empty sections get
  a single `_None yet._` line, never deleted).
- `log.md` got exactly one new line per source.
- No writes outside `00-OS/wiki/`.

## References

- `references/page-templates.md` — exact frontmatter + section templates
- `references/dedup-rules.md` — merge vs append vs flag-conflict logic
- `references/karpathy-pattern.md` — the canonical pattern + gist link
