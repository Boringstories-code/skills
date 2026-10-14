---
name: easy-read
description: "Legibility pass over an EXISTING client-facing deliverable file (site audit, quote, estimate, proposal, scope, upgrade doc, sendable-link page, deck copy): restructure into FRONT (enough to decide) and BACK (enough to check) so a non-technical client can decide from the first screen, with every real finding and number preserved. Runs at one of three intensities — L1 Basic, L2 Don't Have Time (default), L3 ADHD Mode — set at invoke or asked at the start. Structure and density only — voice belongs to humanizer, which runs AFTER. Fires on 'easy-read', '/easy-read', 'run this through easy-read', 'run this through simplifier', 'make this simpler for them', 'make it simple for them to read', 'make this easy for them to read', 'this is too much for the client', 'tighten this for the client', 'they won't read all this', 'basic pass', 'they don't have time', 'adhd mode on this'. Needs a file path — it is a pass over work, not a generator. Manual only, never a gate."
metadata:
  version: '2.0'
---

# easy-read

A pass over a finished client deliverable that cuts the reading without cutting the evidence.

Not a generator. It needs a file that already exists.
Not a gate. It runs when the owner asks, never on its own.
Not humanizer. That skill owns voice; this one owns structure.

## What it optimizes for

The client can decide from the first screen, and verify from the rest.

Thinness is a perception of visible mass, not of word count. An open index reading "24 findings" feels more thorough than 24 open paragraphs, because the client sees the number without paying attention for it. That is the whole trick, and it is how a doc gets lighter to read without getting thinner to justify.

The line that settles edge cases: **cut the reading, never the evidence.** If a change makes the doc lighter and the findings, screenshots, and line items are unchanged, it is right. If it makes the doc lighter and thinner, it is wrong.

## The three levels

The level sets **how hard the doc layers** — never how much survives. Every finding, screenshot, number, and line item lives through all three. What changes is how much a reader has to pass through to reach a decision.

| | L1 Basic | L2 Don't Have Time | L3 ADHD Mode |
|---|---|---|---|
| Front screen | built | built, capped | built, stripped to the four answers |
| Bodies | untouched length | preamble trimmed, kept whole | untouched length, demoted below the index |
| Index | added | added + counted | **is the document** |
| Per finding in the index | one line of what it is | one line of what it is | one line, two max: badge + what's wrong + what it costs |
| Screenshots | in the bodies | in the bodies | under their index row |
| Mast strip | optional | required | required |

### L1 — Basic

Adds structure, moves almost nothing. Build the front screen (verdict, cost of inaction, fix list, price/timeline card, one CTA). Add the index. Bodies stay at their current length, in their current order. Nothing is compressed.

For a client who reads. This is "make it navigable," not "make it short."

### L2 — Don't Have Time  *(default)*

The front/back split enforced. Methodology relocates to the back. Bodies lose their preamble but stay whole. Front lists cap at five with "plus N more, below." Mast strip with the raw counts near the front.

For the normal case: a busy buyer who will skim, decide, and come back to the detail when the invoice lands.

### L3 — ADHD Mode

Every finding becomes **one line, two at most**, in the index: severity badge, what's wrong, what it costs. The index stops being a table of contents and becomes the document — a reader can decide *and* verify from the index alone and never scroll past it. Screenshots move directly under their index row so the proof is visible without a jump.

The bodies still exist below, fully intact, unshortened. Nothing is summarized away. A client who wants the long version scrolls; a client who doesn't, never has to.

Front screen is cut to the four answers and nothing else — no mast strip prose, no framing sentence, no lead-in.

**L3 never drops a body.** If compressing an index row would strand a claim with no body to back it, the row grows to two lines instead. Evidence wins.

### Picking the level

the owner names it at invoke (`/easy-read <file> 3`, `... L3`, `... adhd`, `... basic`). If he doesn't, ask once — level and in-place-vs-alongside in the same question — then go. "Just run it" means L2.

## The model

**FRONT decides. BACK proves.** True at all three levels.

### FRONT — one screen, this order

1. What's wrong, or what's on offer. One sentence.
2. What it costs them if nothing changes. A number where one exists; the plainest concrete stand-in where it doesn't ("eight competitors come up, you don't").
3. What we'd do. Numbered, one line each, five maximum. Anything past five is one line: "plus 5 more, below."
4. Price and timeline, in a card. Always present. When the fix is quoted separately, the card links to the quote.
5. One thing they can do in under two minutes.

No methodology paragraph. No "About this audit." No executive summary above the summary.

At L3, items 1–5 are the entire front screen. Nothing else joins them.

### BACK — in this order

- **The index.** One row per finding: severity badge, plain-sentence heading, one line of what it is, anchor link to its body. Open, never collapsed. This is where the mass becomes visible. At L3 this is the primary read.
- **The bodies.** Flat sections, one per index row, same headings. Screenshots of the actual broken thing live here (at L3, also under the index row).
- **Method, and what we couldn't see.** Last.

## The four rules

### 1. The first screen is the decision

If the client reads only the first screen, they know what's wrong, what it costs them, what it costs to fix, and what to do next. Everything else in this skill exists to make that true.

Bad: an `<h1>` with the client's name, then four paragraphs on how the audit was conducted.
Good: "Your Projects page is blank, and the 18 finished projects behind it can't be found from anywhere. That's the page a prospect opens before they call."

### 2. Move, don't cut

Every real finding survives at every level. Detail relocates from the front to the back; it does not disappear. L3 relocates hardest and still deletes nothing.

The one exception: content with no "should be" is not a finding and gets deleted. A section whose entire body reads "Covered in section six" is filler with a heading on it. Killing it does not drop the count, because it was never in the count.

Report every cut. If something of value got lost, say so and offer to put it back.

### 3. Show the mass with the index

The index is the proof that the work was done. One row per finding, all open, counted on the section label. Add a mast strip near the front with the raw numbers: "39 pages · 6 checks · 4 offices · 11 screenshots." (Optional at L1, required at L2 and L3.)

A screenshot of the actual broken thing beats any paragraph describing it.

Bad: "We conducted a comprehensive review across technical, content, and local dimensions."
Good: the strip, then a screenshot of the empty Projects page with a one-line caption.

### 4. End with one action

One thing, doable in two minutes. Reply with a word, book a slot, send an invite, pay a deposit. Not three options.

The sign-off stays — a client document needs one, and the sign-off *is* the action. Humanizer owns its wording.

Bad: "Rendering was verified in Chrome." (An actual last line from a shipped audit.)
Good: "Reply with the Search Console invite and we start on step 1."

## Do not use `<details>`

It looks like the right instrument and it is not.

- Gmail and Outlook do not render it. A pasted preview shows either nothing or everything.
- Author CSS cannot open a closed `<details>` for print. It needs a `beforeprint` handler, which iOS Share → Print does not reliably fire. A client saving to PDF from their phone gets the evidence stripped out.
- Collapsed proof reads as hidden proof once the invoice lands.

Use the open index instead. It reads on a phone, prints as-is, survives email preview, and Ctrl-F finds things inside it. This holds hardest at L3, where the index carries the whole argument.

## The integrity check

Counting "findings" is not reproducible — the same audit counts 20, 27, or 34 depending on who's counting. Use this instead, which is mechanical:

**Every index row has an anchored body. Every body has an index row.**

Check it by grepping `id=` against `href="#"`. The index count is the count. The count is identical at L1, L2, and L3 — if a level changed it, the level did something wrong.

The operational definition, when a judgment call is unavoidable: a finding is one thing that is wrong with one "should be." Two problems sharing one fix are one finding. One heading holding two different fixes is two findings.

## Both files

the owner's deliverables ship as HTML + MD. Both get the same pass, at the same level, same order, same layering — different instruments. MD gets the front screen, the index (as a list with anchor links), and the flat bodies. HTML gets the cards and badges on top.

They must agree on price, timeline, and the index count. They do **not** have to agree on chrome. At L3, HTML may add a sticky index on desktop and inline screenshot thumbnails; MD renders the same rows as plain text. Substance matches, affordances differ.

If only one of the pair exists, work on that one and note the gap. Do not generate the missing sibling — that is a new deliverable, not a legibility pass.

## Naming the output

When writing alongside rather than in place, the level goes in the filename and in the file:

- `client-site-audit-easy-read-L2.html` / `.md`
- First line of the HTML: `<!-- easy-read: level 2 -->`; MD gets the same as an HTML comment.

Never write "ADHD" into an artifact — it is the spoken trigger, not a label a client sees. Levels are `L1` / `L2` / `L3` on disk, always.

## When to break the rules

1. **Technical buyer.** Default is a non-technical buyer, and the report says so. When the owner says the reader is technical, jargon stays in the headings and the bodies ship expanded. Front and back still hold; the fold just moves. Level still applies on top.
2. **Terms, payment, and scope language.** Format it — card, heading, whitespace — never reword or compress it. Those words are load-bearing in a dispute. **L3 does not compress them either.**
3. **Tiered options.** A quote with three tiers puts all three cards in the front, one visibly recommended. The options *are* the decision. (Don't confuse a quote's tiers with this skill's levels.)
4. **"Keep it long."** Then the pass only adds structure: headings, index, counts, cards, CTA. It moves nothing. That is L1 by another name.
5. **A rule would delete a proof point tied to a line item.** The proof wins. Move it, gloss it, screenshot it. Never cut it. This outranks the level every time.

## Before you hand it back

1. Read only the first screen. Does it answer all four questions — what's wrong, what it costs them, what the fix costs, what to do next? If any is missing, not done.
2. Every index row has an anchored body; every body has an index row. Count unchanged from the source.
3. Every heading is a plain sentence. Read the headings alone, top to bottom. They should tell the story without the body.
4. Price and timeline appear once each, in a card, identical in HTML and MD.
5. **At L3 only:** read the index alone, start to finish. Can a client decide and verify without scrolling into a single body? If not, the rows are still too thin or too fat.
6. Render at 390px wide: every screen has a heading, the CTA is reachable, nothing overflows. Then print preview.
7. Last line is one action, under two minutes.
8. Any new sentence you wrote is flat and declarative, flagged for humanizer.

## Order of operations

**easy-read first. humanizer second. Always.**

Structure decides which sentences exist; voice polishes the ones that survive. Running humanizer first wastes the pass, because this skill rewrites headings, writes new verdict and consequence sentences, and adds CTA copy — all of which would land un-humanized. L3 writes the most new copy, so the humanizer pass matters most there.

- easy-read owns: level, hierarchy, order, layering, density, list length, cards, index, counts, screenshot placement, CTA placement, number placement, mobile and print behavior.
- humanizer owns: word choice, rhythm, AI tells, brand voice, the wording of the sign-off.
- Neither crosses. easy-read writes new copy flat and flags it. humanizer does not reorder, merge, or expand blocks.

Anything client-facing still goes through humanizer before it ships. Any HTML going live still clears the mobile gate.

## Running it

Before touching anything, ask one question covering both: **which level (1 Basic / 2 Don't Have Time / 3 ADHD Mode), and rewrite in place or write alongside?** Skip the level half if the owner already named it at invoke. "Just run it" is L2, in place. Then go.

Report back in the i-have-adhd shape, because the owner is the reader:

- Level run, and why that one fit
- Findings before → after (these should match)
- What was lost
- What's still there
- Anything of value that should come back
- Anything big it cut
- Next: run humanizer, then the mobile check
