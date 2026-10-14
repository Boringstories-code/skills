# The Karpathy LLM-wiki pattern

Source: Andrej Karpathy's gist —
<https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f>

## The core idea

> Instead of just retrieving from raw documents at query time, the LLM incrementally
> builds and maintains a persistent wiki — a structured, interlinked collection of
> markdown files.

Ingestion is **active synthesis, not passive indexing**. Adding a source means the LLM
reads it, extracts the important information, and integrates it into existing pages —
updating entity pages, revising topic summaries, flagging contradictions, strengthening
the evolving synthesis. A single source typically touches 10–15 pages.

## Three layers

1. **Raw sources** — immutable. Dropped in `00-OS/raw/`. Never edited.
2. **Wiki pages** — LLM-generated markdown, densely cross-linked. Live in `00-OS/wiki/`.
   Page types: summaries, entity pages, concept pages, comparisons.
3. **Schema document** — the behavior rules. Here that role is split between
   `00-OS/README.md` (the vault's wiki spec) and this skill's `SKILL.md` + references.

## Navigation files

- **`index.md`** — content-oriented catalog: every page with a one-line summary, by
  category/domain.
- **`log.md`** — append-only chronological record with parseable syntax, one line per
  ingest: date | source | created | updated | domain.

## Knowledge-gap detection (lint)

Periodic health checks identify:

> contradictions between pages, stale claims that newer sources have superseded, orphan
> pages with no inbound links, important concepts mentioned but lacking their own page,
> missing cross-references, data gaps

Then the LLM suggests new questions to investigate and sources to acquire. In this vault,
**dim/stub wikilinks** (links to pages that don't exist yet) are the primary gap signal —
they make missing knowledge visible in Obsidian's graph.

## Merging vs overwriting

**Persistent compilation over re-derivation.** When old and new sources contradict, the
LLM **flags the contradiction explicitly** rather than silently picking a side —
preserving both perspectives for human judgment. Human curation stays central; the LLM
carries the bookkeeping and maintenance burden.

## How this skill applies it

- Aggressive `[[wikilinks]]` per vault `CLAUDE.md` (link on first mention; stubs are good).
- Atomic typed pages (entity / concept / source-summary) per `references/page-templates.md`.
- Merge-not-overwrite + `## Contradictions` per `references/dedup-rules.md`.
- `index.md` + `log.md` maintained every ingest.
- `_morning-review` report (Phase 7) plays the role of the lint pass for this build.
