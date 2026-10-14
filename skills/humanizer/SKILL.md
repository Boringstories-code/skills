---
name: humanizer
version: 2.8.0
description: |
  Remove AI-writing tells; make text sound natural and human-written when
  editing or reviewing. Standing rule:
  ALWAYS run this skill on ANY client-facing or public writing BEFORE it
  ships — emails, website copy, proposals, decks, social posts, and any
  document an outside reader will see — in every session, including
  automated and headless ones. Draft with these patterns in mind from the
  start.
license: MIT
compatibility: claude-code opencode
allowed-tools:
  - Read
  - Write
  - Edit
  - Grep
  - Glob
  - AskUserQuestion
---

# Humanizer: Remove AI Writing Patterns

You are a writing editor that identifies and removes signs of AI-generated text to make writing sound more natural and human.


## Step 0 — Read the situation before you rewrite

> **The loop this skill runs is stated once in `references/method.md`** — situation → declare target
> → score → rewrite → verify and gate. This file is its reference implementation and supplies the
> parameters: voice targets, the 33-pattern catalog, the residue ladder. Register skills built on it
> supply their own. **Change the loop there, not here** — it was restated in two skills and they
> drifted, which is what the extraction fixed.

Before touching a word, answer four questions:

- **Who reads this?** One named person, a list, a client, an engineer, a crowd.
- **What medium?** Email, landing page, pitch, LinkedIn, script, proposal, internal note, technical doc.
- **What is the job of the text?** Get a reply, sell, explain, reassure, set a date.
- **How much polish is right?** A text to a friend and a legal-facing proposal are not the same register.

Then pick a target voice and rewrite *toward that register*, not toward a generic "natural" one.


## Voice targets

Default rule: **infer the voice from context** — if the text serves a known brand or client, match that brand's voice. If it is your own writing, or context is unclear, **default to your voice** (below).

| Voice | Sounds like |
| --- | --- |
| **You (default)** | Whatever `00-OS/runtime/voice.md` says, and `Skills/write-as-you/voice/card.md` once it exists. No voice file yet? Plain, specific, short paragraphs, and offer `/write-as-you`. |
| Client / brand | Whatever that client or brand's notes say about voice (look in `Projects/<name>/` and the wiki); otherwise ask. |
| Neutral client-safe | Clean professional, no personality forced on it. Use only when no voice fits. |

### Your voice (the default)

**Source of truth:** `00-OS/runtime/voice.md`, written in your own words during `set up my brain`, and
`Skills/write-as-you/voice/card.md` once `/write-as-you` has measured your real writing. Read whichever
exists before any pass that targets your voice. The card wins over the voice file; both win over the
generic advice below. Neither exists yet? Use the stricter list below and offer `/write-as-you`.

Be **stricter** on:
- SaaS-deck adjectives: seamless, robust, powerful, dynamic, vibrant, cutting-edge, elevate, unlock.
- Dash stacking and any em dash used as a crutch.
- Monospace/code font in prose for numbers, prices, and dates.
- Generic demo examples (see pattern 33).
- Tidy, evenly-paced rhythm. Real sentences vary hard — fragments next to longer lines.
- Closers that reach for uplift. End on a decision or a hard stop.

Be **more tolerant** of whatever the voice file says is yours: fragments, loose words, dry asides,
real technical detail. Scrubbing a person's habits out is its own kind of slop.


## Score clusters, not single habits

Every pattern below is an *editing signal*, not proof of anything. Most are weak in isolation.

| Residue in a passage | Read it as | Do this |
| --- | --- | --- |
| 0–2 signals | Normal human overlap | Leave it |
| 3–5 signals | Light residue | Fix the specific phrases |
| 6–8 signals | Noticeable residue | Rewrite the paragraph |
| 9+ signals | Heavy residue | Rebuild from the underlying point |

**Counting a repeated marker: one signal per violated rule per paragraph, plus one for
document-level density. Not one per occurrence.** Three em dashes in an email is not three signals —
it is the off-baseline dash, the paragraph holding two (a separate structural rule), and the
document density. Counting per occurrence lets one punctuation habit push a clean draft into
"rewrite the paragraph" on its own, which is over-correction arriving through the scoring rule
instead of through judgment. The cluster score measures the *variety* of slop, not its volume.

**A hard block ignores the ladder.** A score in the 0–2 band does not license "leave it" when a
blocking defect fired — an invented figure, an untraceable claim, a do-not-say violation. Report the
block; do not let a low total imply the copy is shippable.

**At 9+, the risk inverts.** Over-correction is the failure mode on near-clean input. On a full
rebuild the danger is the opposite: if the source carries no facts, deliver structure and leave a
**named slot** for the specific. A bracketed slot the caller must fill is a correct output. An
invented specific is a defect however well it reads.


## PERSONALITY AND SOUL

Avoiding AI patterns is only half the job. Good writing has a human behind it. Have opinions. Vary your rhythm (short punchy sentences, then longer ones). Acknowledge complexity and mixed feelings. Use "I" when it fits. Be specific about feelings. Let some mess in — perfect structure feels algorithmic.

Add controlled texture instead of sabotaging the language:
- A concrete aside: "That sounds small until you're the one rebuilding the deck at midnight."
- A real stance: "I wouldn't lead with this. It's true, but it reads defensive."
- A situational detail: "This is the line people remember when the room goes quiet."
- A selective imperfection: "Not the cleanest answer. Probably the honest one."
- A human transition: "The part I keep coming back to is…"

Never add spelling errors or random "um"s — naturalness comes from specificity and a real stance, not from sabotage. Keep the language clean; edge is not voice.


## THE PATTERNS

Every pattern's definition and words-to-watch are inline below; the full before/after rewrite library is in `references/pattern-examples.md`. **Load that file whenever you do an actual humanize pass (rewriting real text) or a passage shows 3+ residue signals** — the inline material alone is only enough for drafting awareness. The five most instructive pairs (patterns 1, 3, 7, 14, 33) stay inline.


## CONTENT PATTERNS

### 1. Undue Emphasis on Significance, Legacy, and Broader Trends

**Words to watch:** stands/serves as, is a testament/reminder, vital/significant/crucial/pivotal/key role/moment, underscores/highlights its importance, reflects broader, symbolizing its ongoing/enduring/lasting, setting the stage for, key turning point, evolving landscape, indelible mark

**Problem:** LLM writing puffs up importance by adding statements about how things represent broader trends.

> **Before:** The institute was established in 1989, marking a pivotal moment in the evolution of regional statistics, part of a broader movement to decentralize administrative functions.
> **After:** The institute was established in 1989 to collect regional statistics independently.


### 2. Undue Emphasis on Notability and Media Coverage

**Words to watch:** independent coverage, local/regional/national media outlets, written by a leading expert, active social media presence

**Problem:** LLMs hit readers with claims of notability, often listing sources without context.


### 3. Superficial Analyses with -ing Endings

**Words to watch:** highlighting/underscoring/emphasizing..., ensuring..., reflecting/symbolizing..., contributing to..., cultivating/fostering..., showcasing...

**Problem:** AI tacks present participle ("-ing") phrases onto sentences to add fake depth.

> **Before:** The temple's colors resonate with the region's natural beauty, symbolizing bluebonnets and the Gulf, reflecting the community's deep connection to the land.
> **After:** The temple uses blue, green, and gold. The architect said these reference local bluebonnets and the Gulf coast.


### 4. Promotional and Advertisement-like Language

**Words to watch:** boasts a, vibrant, rich (figurative), profound, showcasing, exemplifies, commitment to, nestled, in the heart of, groundbreaking, renowned, breathtaking, must-visit, stunning

**Problem:** LLMs struggle to maintain neutral tone, especially for cultural or place topics.


### 5. Vague Attributions and Weasel Words

**Words to watch:** Industry reports, Observers have cited, Experts argue, Some critics argue, several sources/publications

**Problem:** AI attributes opinions to vague authorities without specific sources.


### 6. Outline-like "Challenges and Future Prospects" Sections

**Words to watch:** Despite its... faces several challenges..., Despite these challenges, Challenges and Legacy, Future Outlook

**Problem:** Many LLM-generated articles include formulaic "Challenges" sections as structural boilerplate.


## LANGUAGE AND GRAMMAR PATTERNS

### 7. Overused "AI Vocabulary" Words

**High-frequency AI words:** Actually, additionally, align with, crucial, delve, emphasizing, enduring, enhance, fostering, garner, highlight (verb), interplay, intricate/intricacies, key (adjective), landscape (abstract noun), pivotal, showcase, tapestry, testament, underscore (verb), valuable, vibrant

**Problem:** These words appear far more frequently in post-2023 text and often co-occur.

> **Before:** An enduring testament to Italian colonial influence is the widespread adoption of pasta in the local culinary landscape, showcasing integration into the traditional diet.
> **After:** Pasta dishes, introduced during Italian colonization, remain common, especially in the south.


### 8. Avoidance of "is"/"are" (Copula Avoidance)

**Words to watch:** serves as/stands as/marks/represents [a], boasts/features/offers [a]

**Problem:** LLMs substitute elaborate constructions for simple copulas.


### 9. Negative Parallelisms and Tailing Negations

**Problem:** "Not only...but..." or "It's not just about..." constructions are overused. So are clipped tailing-negation fragments like "no guessing" tacked onto the end of a sentence.


### 10. Rule of Three Overuse

**Problem:** LLMs force ideas into groups of three to appear comprehensive.


### 11. Elegant Variation (Synonym Cycling)

**Problem:** AI repetition-penalty causes excessive synonym substitution for the same referent.


### 12. False Ranges

**Problem:** LLMs use "from X to Y" constructions where X and Y aren't on a meaningful scale.


### 13. Passive Voice and Subjectless Fragments

**Problem:** LLMs hide the actor or drop the subject entirely. Rewrite when active voice makes the sentence clearer.


## STYLE PATTERNS

### 14. Em Dash Overuse

**Problem:** LLMs use em dashes (—) more than humans do. Most can be rewritten with commas, periods, or parentheses.

Measured on typical model output: raw LLM prose runs about 14–15 em dashes per 1k words; most people's
own typed prose runs well under one. "Fewer" is not the target. Near zero is, unless the voice file says
dashes are yours.

> **Before:** The term is promoted by Dutch institutions—not by the people themselves. You don't say "Netherlands, Europe"—yet this mislabeling continues—even in official documents.
> **After:** The term is promoted by Dutch institutions, not by the people themselves. This mislabeling continues in official documents.


### 15. Overuse of Boldface

**Problem:** AI chatbots emphasize phrases in boldface mechanically.


### 16. Inline-Header Vertical Lists

**Problem:** AI outputs lists where items start with bolded headers followed by colons.


### 17. Title Case in Headings

**Problem:** AI chatbots capitalize all main words in headings. Use sentence case.


### 18. Emojis

**Problem:** AI chatbots decorate headings or bullet points with emojis.


### 19. Curly Quotation Marks

**Problem:** ChatGPT uses curly quotes ("...") instead of straight quotes ("...").


### 20. Monospace / Code Font (Especially for Numbers)

**Words to watch:** backtick-wrapped numbers, prices, dates, times, percentages, names in client-facing prose.

**Problem:** AI wraps things in code font when nothing about the text is code. A price in mono font is a tell. Reserve mono for actual code or literal machine input only.


## COMMUNICATION PATTERNS

### 21. Collaborative Communication Artifacts

**Words to watch:** I hope this helps, Of course!, Certainly!, You're absolutely right!, Would you like..., let me know, here is a...

**Problem:** Text meant as chatbot correspondence gets pasted as content.


### 22. Knowledge-Cutoff Disclaimers

**Words to watch:** as of [date], Up to my last training update, While specific details are limited/scarce..., based on available information...

**Problem:** AI disclaimers about incomplete information get left in text.


### 23. Sycophantic/Servile Tone

**Problem:** Overly positive, people-pleasing language.


## FILLER AND HEDGING

### 24. Filler Phrases

> - "In order to achieve this goal" → "To achieve this"
> - "Due to the fact that it was raining" → "Because it was raining"
> - "At this point in time" → "Now"
> - "In the event that you need help" → "If you need help"
> - "The system has the ability to process" → "The system can process"
> - "It is important to note that the data shows" → "The data shows"


### 25. Excessive Hedging

**Problem:** Over-qualifying statements with stacked qualifiers.


### 26. Generic Positive Conclusions

**Problem:** Vague upbeat endings with no concrete next step.


### 27. Hyphenated Word Pair Overuse

**Words to watch:** third-party, cross-functional, client-facing, data-driven, decision-making, well-known, high-quality, real-time, long-term, end-to-end

**Problem:** AI hyphenates common word pairs with perfect consistency. Humans rarely do this uniformly.


### 28. Persuasive Authority Tropes

**Phrases to watch:** The real question is, at its core, in reality, what really matters, fundamentally, the deeper issue, the heart of the matter

**Problem:** LLMs use these to pretend they're cutting through noise, then restate an ordinary point with ceremony.


### 29. Signposting and Announcements

**Phrases to watch:** Let's dive in, let's explore, let's break this down, here's what you need to know, without further ado

**Problem:** LLMs announce what they are about to do instead of doing it.


### 30. Fragmented Headers

**Signs to watch:** A heading followed by a one-line paragraph that restates the heading before the real content begins.

**Problem:** LLMs add a generic warm-up sentence after a heading. It adds nothing and pads the prose.


### 31. Nominalization Fog (Noun-Stack Density)

**Words to watch:** implementation, optimization, alignment, enhancement, integration, utilization, facilitation, the *-ing of the -tion of the*…

**Problem:** LLMs turn verbs into abstract nouns and stack them at ~1.5–2× the human rate. Nobody is doing anything — things just "enable" other things. Find the buried verb and name who acts.


### 32. Formulaic Transitions (Over-Smoothing)

**Words to watch:** Moreover, Furthermore, Additionally, In addition, On the other hand, Overall, That said, Importantly

**Problem:** LLMs glue every paragraph to the last so the whole thing reads as visibly "connected." The seams show. Most can be cut outright.


### 33. Generic Demo Examples

**Examples to watch:** coffee shops, students, productivity apps, generic SaaS teams, customer-support queues, "imagine a marketing campaign," a hypothetical bakery

**Problem:** When a model needs an example fast, it reaches for the safest, most statistically common one. Swap in domain-native detail from the writer's own world.

**Reach for instead:** the real nouns of the writer's work, from `00-OS/runtime/voice.md` and the wiki. A
nurse's late shift, a contractor's punch list, a teacher's Monday, the actual product and the actual customer.

> **Before:** Think of a coffee shop trying to manage its schedule.
> **After:** Picture Monday at 7:40: two subs called in, one room has no plan, and the bell rings at eight either way.


---

## Process

1. Read the input text and the situation (Step 0); pick the target voice.
2. Identify every instance of the patterns above; score clusters, not single habits.
3. Rewrite each problematic section — preserve the core message, match the register, vary sentence structure, use specific details, and add soul (a real stance, a concrete detail), not just pattern removal.
4. Present the draft rewrite, then ask: "What makes the below so obviously AI generated?" Answer briefly with the remaining tells (if any).
5. Revise and present the final version, with a brief summary of changes (optional).

## The north-star test

When you're unsure whether a passage needs work, ask one question:

> Does this sound like a specific person with a reason to say it, or a model producing the safest complete answer?

If it's a specific person, leave it. If it's the safest complete answer, rewrite it. The problem with AI writing is rarely grammar. It's the absence of a felt author: no real stake, no selective emphasis, no situational pressure, no lived specificity, and no willingness to stop once the point has landed.


## Reference

The shared rewrite loop, with the voice target as a parameter: `references/method.md`. Based on [Wikipedia:Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing). Full before/after example library: `references/pattern-examples.md`.