---
name: second-brain-query
description: Answer questions against the owner's 00-OS Karpathy-style wiki — search the WIKI (not raw sources), synthesize with citations to wiki pages, and optionally file the answer back into the wiki as a new page. Use on '/second-brain-query', '/query', '/q', 'ask the wiki', 'what does my wiki say about X', 'synthesize a comparison of X and Y from my notes'. Read-only on raw/, write-isolated to 00-OS/wiki/.
---

# second-brain-query

Implements Andrej Karpathy's LLM-wiki **query** workflow (see
`references/karpathy-pattern.md` in `second-brain-ingest`, and the gist:
https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) against
the owner's `00-OS/` schema.

## When to use

Trigger phrases: `/second-brain-query`, `/query`, `/q`, "ask the wiki",
"what does my wiki say about X", "synthesize a comparison from my notes",
"what do I know about X", "build me a Marp deck about X from the wiki".

## Input contract

One argument: a **natural-language question or directive**. Optional flags:

- `--domain <a domain listed in 00-OS/wiki/index.md, or all>` — restrict the search. Default `all`.
- `--depth <shallow|standard|deep>` — controls how many pages to read and how
  much follow-up wikilink traversal to do. Default `standard`.
  - `shallow` = direct hits only, <= 10 pages.
  - `standard` = direct hits + 1 hop on wikilinks, <= 30 pages.
  - `deep` = direct hits + 2 hops, may read up to 60 pages.
- `--format <answer|table|marp|chart|canvas|page>` — output shape. Default `answer`.
  - `answer` — markdown prose answer in the chat.
  - `table` — comparison table.
  - `marp` — Marp slide deck saved to `Inbox/`.
  - `chart` — matplotlib chart saved to `Inbox/`.
  - `canvas` — Obsidian `.canvas` file saved to `00-OS/wiki/_canvases/`.
  - `page` — file the answer back as a new wiki page (see `file-back-rules.md`).
- `--file-back` — even when `--format` isn't `page`, also save a wiki page version.
- `--unattended` — skip clarifying questions; use best judgment.

## Behavioral spec

1. **Parse the question.** Identify key entities/concepts likely to be wiki pages.
   Generate 3–7 candidate slugs (kebab-case) to look up first.
2. **Search the wiki** under `00-OS/wiki/<domain>/` (or all domains if `--domain all`):
   a. Direct slug hits (fastest).
   b. `_index.md` lookups per domain.
   c. Wikilink traversal — follow `[[...]]` from hit pages up to depth limit.
   d. **Full-text search** as fallback (`rg` over `00-OS/wiki/`).
3. **NEVER read `00-OS/raw/`.** Raw sources were the ingestion input; querying
   them defeats the purpose of the wiki layer. If the wiki lacks info, say so
   and suggest a `/second-brain-ingest` of a specific raw file.
4. **Read the relevant pages** and assemble context. Track every page used.
5. **Synthesize the answer:**
   - Direct, no hedging.
   - **Every factual claim cites the wiki page it came from** as `[[page-slug]]`.
   - Flag contradictions found between pages — do NOT silently pick one.
   - If sources within a page conflict (a `## Contradictions` section), surface
     that to the user.
   - If the wiki has gaps, name them: "Wiki has no page for X — suggest ingesting Y."
6. **Output** per `--format` (see `references/output-formats.md`).
7. **File-back** (if `--format page` or `--file-back`):
   - Pick a slug. Default location: `00-OS/wiki/<domain>/_synthesis/<slug>.md`.
   - Use the **synthesis page template** in `references/output-formats.md`.
   - Frontmatter `type: synthesis`, `source-pages: [list of [[wikilinks]] used]`,
     `generated-by: second-brain-query`, `created: YYYY-MM-DD`.
   - Append one line to `00-OS/wiki/log.md`:
     `YYYY-MM-DD HH:MM | QUERY: "<question>" | <N> pages read | <synthesis-slug>`
   - Update the domain `_index.md` under a new `## Synthesis pages` section.

## Search strategy (see `references/query-patterns.md`)

The skill should use a layered search:
1. **Slug guess** — if the question mentions "USB-C", try `usbc.md`, `usb-c.md`.
2. **`_index.md` scan** — domain index files list every page with a one-liner.
3. **Wikilink graph walk** — once a seed page is found, follow its links.
4. **Full-text `rg`** — last resort for fuzzy matches.

## Write-isolation (hard rule)

- **Only write under `00-OS/wiki/`** — same as ingest.
- **Never** modify wiki pages that already exist. The query skill ONLY creates
  new pages in `_synthesis/` subdirectories or in `Inbox/` (for Marp /
  charts / canvas / non-wiki outputs).
- Modifying an existing wiki page is the ingest skill's job, not the query
  skill's. If a query answer materially updates an existing page's facts,
  flag it: "Suggest re-running /second-brain-ingest on <source> to update [[page]]."

## Output formats (full templates in `references/output-formats.md`)

### `answer` (default)
Markdown prose in chat. Citations are `[[wiki-page]]` wikilinks. Followed by:
```
---
**Wiki pages read:** [[page-1]], [[page-2]], …
**Gaps found:** none / list
**Contradictions surfaced:** none / list
```

### `table`
Markdown comparison table. Column headers wikilink to the wiki pages compared.
Cells cite specific source pages.

### `marp`
Marp markdown deck saved to `Inbox/marp-<slug>-YYYY-MM-DD.md`.
Each slide cites wiki pages. Title slide names the question. Closing slide
lists all wiki pages used.

### `chart`
Python script that generates a matplotlib PNG. Save both `.py` and `.png` to
`Inbox/`. Chart title = question. Data sourced from wiki pages (frontmatter
or table parsing). Footer text: "Source: 00-OS/wiki, generated YYYY-MM-DD".

### `canvas`
Obsidian `.canvas` JSON file. Nodes = wiki pages. Edges = wikilink relationships
relevant to the answer. Save to `00-OS/wiki/_canvases/<slug>.canvas`.

### `page`
Full markdown wiki page using the synthesis template (see `references/output-formats.md`).
Filed at `00-OS/wiki/<domain>/_synthesis/<slug>.md`.

## Modes

- **Interactive**: may ask "Restrict to a domain?" or "Should I file this back as a page?"
- **`--unattended`**: pick sensible defaults. Default `--format answer`.

## Quality bar (self-check)

- Every factual claim is wikilinked to a wiki page.
- No claim is invented or sourced from the assistant's general knowledge —
  if the wiki doesn't have it, say so.
- Output names the pages it read.
- Output names the gaps it found.
- No writes outside `00-OS/wiki/` or `Inbox/`.
- If `--format page`, log line was added.

## References

- `references/query-patterns.md` — search strategy, slug-guessing heuristics, hop budgets
- `references/output-formats.md` — exact templates for each `--format`
- `references/file-back-rules.md` — when to file back, where, frontmatter rules
- `../second-brain-ingest/references/karpathy-pattern.md` — canonical pattern reference
