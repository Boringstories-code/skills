# Query patterns — slug guessing & search strategy

## Slug-guess heuristics

When the user asks "what does my wiki say about sourdough hydration", generate candidate slugs:

1. **Exact** — `sourdough-hydration`, `sourdough`, `hydration`
2. **Variants** — `sourdough-water-ratio`, `dough-hydration`
3. **Strip articles** — "the Roth conversion" → `roth-conversion`, `roth`, `conversion`
4. **Hyphenate caps** — "USBC Power Delivery" → `usb-c-power-delivery`, `power-delivery`, `usbc`, `usb-c`

Look for each candidate under all three domains unless `--domain` restricts.

## Hop budget

- **shallow**: read up to 10 pages, no wikilink hops past the first match.
- **standard**: 1 hop. From each seed page, follow `[[…]]` to pages whose title appears in the question.
- **deep**: 2 hops. Used for "compare X and Y across multiple dimensions" or "what's the relationship between A, B, C".

Stop hopping when you've read 30 pages (standard) or 60 (deep) regardless of remaining links.

## Full-text fallback

If slug-guess + `_index.md` + wikilink walk yields <2 pages, run:

```bash
rg -l -i '<key-term>' 00-OS/wiki/
```

Read top 10 matches. If still empty, return: "Wiki has no coverage of <topic>.
Closest pages are [[…]], [[…]]. Suggest ingesting a source on <topic>."

## Contradiction handling

If two pages disagree, **surface both** in the answer:

> The wiki disagrees on this point:
> - [[page-a]] claims X (source: `foo.md`, 2026-04-15)
> - [[page-b]] claims Y (source: `bar.md`, 2026-05-22)
> Recommendation: re-ingest the newer source, or run `/wiki-lint` to flag.

## Stub-page handling

A wiki page with only frontmatter + `_None yet._` is a stub. Treat as "concept
exists, content missing". Surface to user: "[[stub-page]] is a known concept
but has no content — suggest ingesting a source on it."
