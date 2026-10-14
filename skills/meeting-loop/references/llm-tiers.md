# How much LLM does this actually need?

Short version: **the engine needs none, the value needs some, and only one thin lane needs a frontier
model.** The pipeline has a clean seam between deterministic work and judgment work. Knowing where that
seam falls is what lets the same skill serve an air-gapped clinician and a full cloud install.

## The seam

**No LLM. Never. Pure code.**

| Stage | Why it's LLM-free |
|---|---|
| Transcription | Whisper is a speech model, not a language model. Local, no API, no egress. |
| Two-mic attribution | `diarize_two_mic.py` compares energy across recorders — *"needs no model at all and no gated weights."* Best attribution method in the skill, and the one with zero ML. |
| Acoustic diarization | Embeddings + clustering (pyannote / Resemblyzer). Not an LLM. |
| Diarization scoring | Arithmetic against a majority baseline. |
| Hallucination-loop stripping | Deterministic post-processing in `transcribe.py`. |
| Routing, folder mapping, privacy routing | Profile lookups. Table-driven. |
| Merge strategies | `append-dated-block` and friends are file operations. |
| Retention, consent surfacing, collision handling | Rules. |
| HTML + JSON render | stdlib. |
| Tier 0 detection | bash. |
| Type classification | Can degrade to keyword/regex against each type's `signals` + the filename. Worse than a model, but it works. |

**Needs an LLM, and the required tier rises with what you want out of it:**

| Stage | Tier that suffices | Why |
|---|---|---|
| Transcript cleaning, paragraphing, filler removal | **small** | Mechanical. This is also 90% of the tokens — long inputs, parallel, latency-dominant. Economize here. |
| Action-item extraction | **small–mid** | A mid model gets most items. It misses implied commitments and over-extracts politeness ("yeah I'll take a look"). |
| Decisions + owner assignment | **mid** | Needs to track who said what across a transcript. |
| "What they said vs what they actually want" | **frontier** | This is the whole point of the client mode and it is genuinely hard. A mid model produces a competent summary of the wrong thing. |
| Living-note merge + conflict resolution | **frontier** | Merges are near-irreversible in a knowledge base. Wrong merges are silent. |
| Concept dedup against an existing wiki (L2) | **mid–frontier** | Requires semantic search plus the judgment to merge rather than create. Duplicate pages are how a wiki dies. |
| Durable-belief vs meeting-noise (Channel C) | **frontier** | Small models mint cards from small talk. |
| Execution planning (Step 8f) | **frontier** | Reversibility flags, one-way-door detection, client-facing detection. Being wrong here sends an email you can't unsend. |
| The setup grill's *recommendations* | **mid–frontier** | Any model can read nine questions aloud. Recommending the right answer from detected context is the value. |

## The three usable configurations

**`mode: none` — deterministic only.** You get: transcript, speaker attribution (excellent with two mics,
honest `SPEAKER:` labels otherwise), correct filing, privacy routing, retention, and a **candidate**
action-item list from rule-based extraction — imperative sentences, first-person commitments, direct
asks. Call it what it is: a list a human triages, not a finished one. Hard-capped at **L0** — entity
merges and concept dedup are judgment, not string matching. Genuinely useful. Not the product.

**`mode: local` — on-device model.** Ollama or llama.cpp on the same Mac. Everything stays on the
machine. Quality lands around the mid tier: clean transcripts, decent action items, workable entity
notes. **This is the configuration the clinician persona requires** — an air-gapped encrypted volume
means transcripts cannot go to a cloud API at all, so `egress_allowed: false` forces this path. Realistic
ceiling: **L1**.

**`mode: split` — the recommendation, and what the skill already does.** Small/fast model on the volume
lane, frontier on the thin judgment lane. The existing two-tier table (fable breadth for cleaning and
triage, opus depth for synthesis, merges, and planning) is exactly this. Cheap where the tokens are,
expensive where the mistakes are. Supports **L2**.

## Direct answers

**Can it work without an LLM?** Yes, and more of it than you'd guess — transcription, the best speaker
attribution, all the routing and privacy machinery, and rule-based candidate items. But without an LLM
it's a good transcription-and-filing tool, not a meeting loop. The loop closes because something reads
the conversation.

**Is a basic LLM fine?** For most of the run, yes — cleaning is the bulk of the work and a small model
does it well. Where a basic model actually costs you: intent decode, note merges, and execution
planning. All three fail *quietly* — you get a fluent, plausible, wrong artifact, which is worse than an
obvious failure because you'll act on it.

**Does it need frontier?** Only on the judgment lane, which is a small fraction of tokens. Paying
frontier prices to clean a 90-minute transcript is waste; paying small-model prices to decide what a
client actually wants is false economy. Split the lanes and you get most of the quality for a fraction
of the cost.

**Rule of thumb:** model tier should track `distillation.level`. L0 → none or small. L1 → local or mid.
L2 plus execution → frontier on the judgment lane, always.
