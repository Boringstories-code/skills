# Concept card — schema, template, gate

A concept card is the unit of *understanding*, as opposed to the wiki's unit of *knowledge*
(entity, claim) or Life's unit of *identity* (belief). It answers: what is true here, **why**, how
do I know, what does it connect to, what don't I know yet, and what do I do differently.

Lives at `00-OS/wiki/concepts/<slug>.md`. One concept per file. Slug = kebab-case, no dates.

## What qualifies as a concept (and what doesn't)

A concept is an **explanation that transfers** — it would still be useful in a different meeting,
a different client, a different year. Ask: would a smart stranger who never saw the source learn
something here they could act on?

Not a concept — route elsewhere:
- **Action item** ("send the deck Tuesday") → `action-items.md`.
- **Entity fact** ("a Roth IRA has an annual contribution limit") → wiki entity page, `/second-brain-ingest`.
- **Owner belief** ("I'd rather be honest than impressive") → `Life/`, Channel C.
- **Fact about a person** → `People/`, Channel B. Never here.
- **Trivia** — true, but changes nothing. Skip.

0–4 cards from a rich source is a normal harvest. Zero is a normal outcome. Never pad.

## Template

```markdown
---
title: <Concept Name>
type: concept-card
domain: concepts
claim: "<one falsifiable sentence>"
aliases: []
source: <primary-source-slug>
sources: [<source-slug>]
edges:
  - {type: <see edge-vocabulary.md>, to: "[[slug]]", note: "<why>", source: "<source-slug>"}
confidence: low        # low = one source · medium = 2+ independent sources · high = tested in own work
status: forming        # forming · held · contested · retired
topics: [<lane tag>, <lane tag>]
relates-to: ["[[slug]]"]
ingested: YYYY-MM-DD
created: YYYY-MM-DD
updated: YYYY-MM-DD
tags: [concepts, concept-card]
---

# <Concept Name>

## Claim
<The same one sentence as frontmatter `claim`. Falsifiable: someone could show it wrong.>

## Mechanism
<WHY and HOW it works. Plain language a smart stranger follows without the source's jargon.
If the source only asserts and never explains, say so — "source asserts, mechanism unknown" —
and put the how in Open questions. Do not restate the claim with more words.>

## Evidence
- "<verbatim quote>" — <role, not name> · <source-slug> · YYYY-MM-DD
- <observation from the owner's own work, dated> (source: <slug>)

## Connections
- **<type>** → [[slug]] — <one line why>

## Open questions
- <What would change my mind? What can't I explain yet? What haven't I tested?>

## So what
<What the owner does differently because this is true. Concrete. If nothing, this is trivia — delete
the card.>

## Contradictions
_None yet._

## Sources
- [[_sources/<source-slug>]]
```

## The gate (Feynman check) — a card that fails is not written

`scripts/concepts.py lint` enforces the mechanical half. You enforce the judgment half.

Mechanical (linter, exit 1 on any):
1. Frontmatter `claim` is one sentence, non-empty; body `## Claim` present.
2. `## Mechanism` non-empty and not a paraphrase of the claim (linter: must be longer than the
   claim and not contain it verbatim).
3. `edges` has ≥1 entry; every `type` is in the closed vocabulary; every `to` is a `[[wikilink]]`;
   every edge target appears in `## Connections`.
4. `## Evidence` has ≥1 quoted line (contains `"`), each with a source slug.
5. `## So what` non-empty.
6. `## Open questions` has ≥1 bullet. (Understanding with no open loop is either finished
   science or unexamined — both rare.)
7. `confidence` ∈ {low, medium, high}; `status` ∈ {forming, held, contested, retired}.
8. No `People/` path, and no name that appears in `People/_names.md` — evidence uses roles.

Judgment (you, before writing):
- **Restate test.** Can you say the mechanism in one plain sentence to someone outside the field?
  If you need the source's vocabulary to say it, you don't understand it yet — that goes in Open
  questions, and the card's `status` stays `forming`.
- **Transfer test.** Name one situation *outside* the source where this applies. Can't? Not a
  concept.
- **Prediction test.** Does the card imply something checkable? If yes, that's a `predicts` edge or
  an Open question. If nothing is checkable, confidence can never rise past `low` — say so.
- **Cost test.** Every lever has a tradeoff. No `cost-of` edge and no cost in Open questions is a
  smell.

## Privacy

- Cards are wiki pages (shared layer). **Nothing from `People/` ever appears** — not a name, not a
  fact. Speakers are roles: "the client", "the coach", "the editor".
- Evidence from `Life/` is not copied. A card may carry an `instance-of` edge to `"[[t-…]]"`; the
  words stay in `Life/`.
- Client meetings produce **client-neutral** cards (same rule the wiki already uses: "concept-only,
  client-neutral"). The client's name may appear in provenance only — the `source:` / `sources:`
  fields, edge `source:` slugs, and the `[[_sources/…]]` link — never in the card's prose, title,
  aliases, or evidence attributions. The `_sources/` page names the meeting; the card names the
  concept.

## Dedup — one concept, one card

Before minting, `rg -il "<two or three subject terms>" 00-OS/wiki/concepts/` and read the hits.
- **SAME** → merge: append evidence with provenance, add the source to `sources:`, re-evaluate
  `confidence` (2+ independent sources → `medium`), bump `updated`. Do not mint.
- **OPPOSED** → do not fork. Add a `contradicts` edge on the existing card pointing at the new
  source's claim (written as a new card only if it stands on its own), record both under
  `## Contradictions`, set `status: contested`.
- **RELATED** → mint, and link both ways with the right edge type.
- **NONE** → mint.
- **Unsure** → mint nothing; add the candidate to `## Review needed` on the nearest card.

## Lifecycle

`forming` (one source, mechanism shaky) → `held` (mechanism restates cleanly, 2+ sources or tested)
→ `contested` (a live `contradicts` edge) → `retired` (the owner decided it's wrong; keep the card,
say why — a retired card is a learning too).
