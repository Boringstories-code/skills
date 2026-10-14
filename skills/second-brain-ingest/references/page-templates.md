# Page templates

Exact frontmatter + section templates for every page type the ingest skill writes.

**Frontmatter is a reconciled superset** of the `00-OS/README.md` wiki schema (which
specs `source / ingested / topics / entities / relates-to`) and the overnight plan's
typed schema (`type / domain / aliases / sources`). Both are honored so the pages
satisfy the README, the plan, and the vault `CLAUDE.md` standard frontmatter at once.

Rules:
- `kebab-case` slug filenames, no dates in filename (dates live in frontmatter).
- `source:` = the primary raw filename this page came from. `sources:` = the full array
  of every raw source that has contributed (grows on merge).
- `relates-to:` holds wikilinks to sibling pages. Mirror important relationships on both
  pages.
- Empty body sections get a single `_None yet._` line — never delete a section.
- All wikilinks resolve by filename, not path. Dim links to non-existent pages are
  intentional stubs.

---

## Entity page — `00-OS/wiki/<domain>/<slug>.md`

```markdown
---
title: <Human-Readable Name>
type: entity
domain: <a domain listed in 00-OS/wiki/index.md>
aliases: [<alt name>, <abbreviation>]
source: <primary-raw-filename.md>
sources: [<source-slug>]
topics: [<tag>, <tag>]
entities: []
relates-to: ["[[related-page]]"]
ingested: YYYY-MM-DD
created: YYYY-MM-DD
tags: [<domain>, entity]
---

# <Human-Readable Name>

## Overview
<2–4 sentences: what it is, why it matters in this domain.>

## Key facts
- <fact> (YYYY-MM-DD source: <slug>)

## Related concepts
- [[related-page]] — <one line on the relationship>

## Open questions
- <gap or unknown surfaced by this source>

## Sources
- [[_sources/<source-slug>]]
- <external URL/ref cited in the raw file, if any>
```

---

## Concept page — `00-OS/wiki/<domain>/<slug>.md`

```markdown
---
title: <Concept Name>
type: concept
domain: <a domain listed in 00-OS/wiki/index.md>
aliases: [<synonym>]
source: <primary-raw-filename.md>
sources: [<source-slug>]
topics: [<tag>, <tag>]
entities: []
relates-to: ["[[related-page]]"]
ingested: YYYY-MM-DD
created: YYYY-MM-DD
tags: [<domain>, concept]
---

# <Concept Name>

## Definition
<1–3 sentences. Precise.>

## How it works
<mechanism / steps / structure>

## Examples
- <concrete example, ideally tied to an [[entity]]>

## Common pitfalls
- <mistake people make>

## Related
- [[related-page]] — <relationship>

## Sources
- [[_sources/<source-slug>]]
```

---

## Source-summary page — `00-OS/wiki/<domain>/_sources/<source-slug>.md`

```markdown
---
title: "Source: <original raw filename>"
type: source-summary
domain: <a domain listed in 00-OS/wiki/index.md>
source: <raw-filename.md>
ingested: YYYY-MM-DD
created: YYYY-MM-DD
tags: [source-summary, <domain>]
---

# Source: <original raw filename>

## What this source is
<1–2 sentences: origin, scope, kind of document.>

## Key takeaways
- <the 3–8 most important things this source contributes>

## Pages generated
**Created:**
- [[<slug>]]

**Updated:**
- [[<slug>]]

## References cited inside
- <URL/ref>, or `_None._`
```

---

## Contradictions block (added to any page when a new source conflicts)

```markdown
## Contradictions
- <claim A> (YYYY-MM-DD source: <slug-A>) **vs** <claim B> (YYYY-MM-DD source: <slug-B>)
```

## Review needed block (added in `--unattended` mode for any ambiguity)

```markdown
## Review needed
- <what was ambiguous and the judgment call made, so the owner can confirm or correct>
```
