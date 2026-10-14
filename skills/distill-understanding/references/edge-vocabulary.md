# Edge vocabulary — the closed set

A concept card connects to other pages through **typed edges**. Untyped wikilinks say "these are
related." A typed edge says *how* — which is the difference between a note and understanding.

Eight types. Nothing else is valid; the linter rejects anything off this list. If a relation
doesn't fit, it is probably two relations, or it isn't one yet — leave it in `## Open questions`.

| Type | Reads as | Test before you write it |
|---|---|---|
| `causes` | A reliably produces B | Remove A and B stops happening. Correlation alone fails this. |
| `enables` | A makes B possible or cheap, but doesn't force it | B can happen without A, just worse / dearer / rarer. |
| `requires` | A cannot happen without B | You've seen A fail for lack of B, or can say exactly why it would. |
| `contradicts` | A and B cannot both be true as stated | Cite both sources. **Never resolve** — record both, set `status: contested`. |
| `generalizes` | A is the broader principle; B is one case of it | You can name at least one *other* case of A besides B. |
| `instance-of` | A is a concrete case of B | Inverse of `generalizes`. Also how a card points at a wiki entity page or a `Life/` thought id. |
| `predicts` | If A holds, expect to observe B | B is something you could actually check next week. This is the falsifiability hook. |
| `cost-of` | B is the price or tradeoff of A | Every real lever has one. A card with a `causes` and no `cost-of` is usually half-thought. |

## Rules

- **Direction matters.** `from` is always the card you're writing. `to` is the target.
- **Targets are wikilinks**: `"[[slug]]"`. Concept cards, wiki entity/concept pages in any domain,
  or a Life thought id `"[[t-…]]"`. A dim link to a page that doesn't exist yet is a deliberate stub
  and the weekly brief reports it as a gap.
- **One line of `note` per edge** — why you believe the relation, in plain words. An edge with no
  note is a guess.
- **`source`** on every edge — the source-slug it came from. Two sources asserting the same edge
  independently is how `confidence` climbs.
- **Never write `contradicts` and then pick a winner.** Karpathy rule, same as the wiki: flag,
  don't silently resolve. the owner resolves in the brief, or time does.
- **Mirror the important ones.** If A `causes` B and B is a card, B's `## Connections` gets a
  line back. The linter doesn't enforce mirroring; the brief reports one-way edges.

## Format (frontmatter)

```yaml
edges:
  - {type: causes, to: "[[slug]]", note: "one line why", source: "<source-slug>"}
  - {type: cost-of, to: "[[other-slug]]", note: "…", source: "<source-slug>"}
```

Body `## Connections` mirrors each edge as one readable line:

```
- **causes** → [[slug]] — one line why
```
