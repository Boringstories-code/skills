---
title: "Marker spans — flagging work out loud mid-meeting"
type: reference
created: 2026-09-17
source: meeting-loop
tags: [meeting-loop, channel-d, handoff]
---

# Marker spans — flagging work out loud mid-meeting

Channel D pulls AI work out of a tape two ways. It always *infers* — any line addressed to an agent
("have Claude redo the deck") gets caught on its own. A **marked span** is the deliberate version: you
hand the floor to an agent, say whatever you want for as long as you want, then take the floor back.
Everything in between becomes handoff items even when no agent is named and the lines are bare goals.

The extractor reads for intent, not for a phrase list. So there is no magic word to remember wrong —
but a few habits make the difference between a clean item and a grill question.

## The gesture

**Open** — hand any tool the job, at the start of what you're saying:

> "Okay, let's have Claude take care of this."
> "Get Grok to do this one."
> "Have Codex handle that."
> "I'm going to hand this to the agent."

Any tool you actually use works — Claude, Grok, Codex, "the agent", "the AI", or something this install has
never heard of. Name a tool it doesn't know (Cursor, Devin) and it still gets captured, slugged as you said
it, with its own section in the handoff.

**Close** — take the floor back:

> "That's all for Claude."
> "Okay, we're done with that."
> "Alright, back to us."

Close and then keep dictating in the same breath and it still works — the phrase marks intent to stop, so the
span ends where the instructions actually stop, and the grill tells you where it landed.

Anything goes as long as the intent is plain. Saying it a new way every time is fine — there is no phrase
to memorize, and none of these is magic. What the loop reads for is the shift: you stop talking to the room
and start dictating to a machine, then stop.

## What to do inside the span

**Talk in whole sentences.** The span is going to a cold agent that has none of the room's context.
"That thing we said" produces a useless item; "the Christmas kids' medley, two to three minutes" produces
a real one.

**Separate your tasks out loud.** "First… Next… Last one…" — one span can hold several jobs, and they
come out as several items in the order you said them. Without the seams it may land as one lumpy item.

**Say the constraints while you're in there.** Who it's for, when it's due, what it must not do. Those
become the item's `capability` line, which is the whole contract the receiving agent works from.

**Name the tool in the opening if you care which one.** "Let's have Grok take care of this" routes the whole
span to Grok. Otherwise it goes to your default target.

**Switch tools mid-span without closing.** "…and then get Grok to do the research on that" sends the rest to
Grok. One span can feed several agents; the handoff gives each its own paste block, so you paste the Claude
work into Claude and the Grok work into Grok without sorting anything by hand.

## What breaks it

**Quoting the cue.** Saying *"I could just say 'hey Claude' and it'd pick it up"* is a description, not a
use. The spec is explicit about this, so it won't open a span — but don't expect a demo to flag itself.

**Forgetting to close.** If you get interrupted and never close it, the span ends where the dictating stops —
the last instruction aimed at a machine, before the talk goes back to the room — and the grill gets a question
naming where it cut and why. You lose nothing, you answer one question later. It will never run an open span
to the end of the tape.

**Spoken slashes.** "Slash slash" is not a cue and never will be — on your tapes that phrase is almost
always you explaining slash-commands to somebody ("you just slash slash model"), and "slash" shows up
mid-word in ordinary speech ("kids-slash-family moment"). A literal `//` at the head of a line in a text
source still opens a span; the spoken form never does.

**Naming an agent in passing.** "Claude's been good lately" opens nothing. Neither does "have Claude redo
the deck" — that is an ordinary explicit command, it sets the target and gets captured, but it isn't a
marked span. Marking is reserved for the deliberate gesture, otherwise the flag would mean nothing.

**Someone else opening one.** Only you can open a span. A colleague saying "maybe Claude can help with this" is
captured as a normal item flagged for your confirmation, not as a span. But once *you* have one open and she
talks inside it and you take up what she said, that gets captured too — flagged for confirmation, and marked.

## What you get

Marked items carry `marked: true` and show up in `ai-handoff.md` tagged *(flagged live by a spoken cue)*,
in both the item list and the paste block, so you can see at a glance that the loop honored what you said
on the tape. Everything else about the handoff is unchanged — waves, gates, grill, per-target paste blocks.

A tape with no span behaves exactly as it always has. The gesture is optional, always.

## Worked example

> **the owner:** Okay, hey Claude, take care of this for me. First, pull every song we've played in the last
> six months out of PCO with play counts. Second, I want a one-page HTML doc with five service options for
> Christmas Eve, using our brand kit — that's for Dana, so keep it readable, not a spreadsheet.
> And then get Grok to price out a string trio for three days of services in 2026, just a rough average.
> That's all for Claude.
> **the owner:** Anyway, so what were you saying about the candy canes?

Three items, all `marked: true`. The first two go to `claude`, the trio pricing to `grok` — two paste blocks
in the handoff, each with that agent's own note, nothing to sort by hand. Span closed cleanly, and the candy
canes stay out of it.
