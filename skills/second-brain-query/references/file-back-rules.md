# File-back rules — when to save a query answer to the wiki

## When to file back automatically (`--format page` triggers this)

- The user asked a comparison or synthesis question with **lasting value**:
  "compare X and Y", "what's the difference between A and B", "summarize all
  my notes about X", "what's my position on X".
- The answer drew on **>= 3 wiki pages** and synthesized something not stated
  on any single one.

## When NOT to file back

- One-off lookups: "what's the Roth IRA limit this year" → just return the answer.
- Questions answered by a single wiki page — that page is already the source of truth.
- The answer contains time-sensitive info that will be stale in a week.

## Where to file back

`00-OS/wiki/<domain>/_synthesis/<slug>.md`

The `_synthesis/` subdirectory keeps query-generated pages distinct from
ingestion-generated entity/concept pages. Both are valid wiki content,
but their provenance differs.

## What about cross-domain syntheses?

If the answer spans two domains (e.g., "how does my side income change what
I can put in a Roth IRA"), file at `00-OS/wiki/_cross-domain/<slug>.md` with
`domain: cross` in frontmatter.

## Slug rules

Same as ingest: kebab-case, no dates, stable names. Synthesis slugs should
**not** collide with entity/concept slugs. Prefix with a question-shaped phrase
if collision would happen:
- Entity: `roth-ira.md`
- Synthesis: `roth-vs-traditional-ira-comparison.md` (not `roth-vs-traditional-ira.md`, which
  could itself be an entity)

## Log line format

```
YYYY-MM-DD HH:MM | QUERY: "<question, truncated to 80 chars>" | <N> pages read | filed: <synthesis-slug>
```

## Re-querying same topic

If a synthesis page exists for the same question, **read it first**. If the
underlying wiki pages have changed since (compare `created` dates), generate
a new version with `-v2`, `-v3` suffix and link both: "supersedes [[prev-version]]".
