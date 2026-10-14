---
name: meeting-loop
description: >-
  Turns any meeting/call/session recording (.wav/.flac) into a speaker-attributed transcript
  plus the right action items, filed in the right home — and on your explicit go, EXECUTES
  them (drafts the email, makes the site change) so you approve instead of do. Classifies the
  recording (client, personal, creative/music, work, dev/build) and confirms rather than guessing.
  On a dump of several Voice Memos, proposes which files are the same sitting and waits for
  confirm before full transcribe. Local mlx-whisper, People-firewalled. Fires on 'transcribe
  this/these recordings', 'process this meeting', 'action items from this call/session',
  'what do I need to do from this audio', a pointed-at recording, or 'richest version'
  (opt-in rich branch).
---

# Meeting Loop

Turn a recording of a meeting, call, or session into a clean transcript + the right action items +
any living note, routed to the right home for whatever KIND of meeting it is. "Client" is one mode,
not the whole skill — a friend catch-up, a songwriting session, or an internal planning call each get
their own routing and lens. The engine underneath (local transcription, speaker attribution, People
enrichment, privacy routing) is the same for all of them.

## The one rule: ask, don't assume

Clarity is the whole point. On a dump of several recordings, **propose which files are the same
sitting and confirm that first** (Step 1) — then propose a type. The router **proposes** a type and
**confirms** it — one word from the owner switches it. Routing targets (which client, which band/group/artist,
which project, which brand) are **always asked, never inferred**. When the type is unclear or looks new,
ASK the owner what it is and offer to save it as a new type. A wrong-but-confident guess is worse than a
quick question.

## Meeting types (extensible)

`meeting-types.json` (beside this file) is the registry. Each type carries: `signals` (how to spot it),
`home` (where output lands), `clarify` (questions to ask before routing), `output_shape`, `lens`,
`people_enrich`, `sensitive_default`, and `extras`. Built-in at launch:

- **client** — client meeting/call/site visit → the client's folder (its `home`), two-sided action items, living profile, optional PDF/HTML.
- **personal** — friend / chill 1:1 → the personal notes folder (its `home`). Light notes, sensitive-by-default.
- **creative** — music / writing / co-write session → the band/project folder (ASK which). Session note, not client deliverable.
- **work** — internal / brand / generic meeting → the project's folder (ASK which) or `Inbox/`. Decisions + owner-tagged action items.
- **dev** — build/code session → the project's repo or notes folder (ASK which project). Grill-ready `build-brief`; Offer `/build` on the brief when there's something to build.

**New types are data.** When the classifier can't match confidently, it asks the owner to name the type,
asks the few facts it needs (home, output shape, People-enrich?, sensitive?), and **appends a new entry
to `meeting-types.json`** (reviewed edit) so it's known forever after. The registry grows with use.

## What this skill produces (mode-parametric)

Every run yields a **clean, speaker-attributed transcript** + raw backups (privacy-routed, see Step 8).
On top of that, the resolved type's `output_shape` decides the rest:

- **two-sided-action-items** (client): `action-items.md` — My side / Their side / Clarity questions / products-pricing. Plus a living `client-profile.md`.
- **light-notes** (personal): a short note of my to-dos + what's worth remembering; enrichment folds into that person's note.
- **session-note** (creative): ideas, hooks, directions tried, creative to-dos, references — filed to the band/project. Plus a local chord chart (`chords.md`) from Basic Pitch when the tape has music.
- **decisions-and-action-items** (work): decisions + action items by owner + open questions → the project's folder or Inbox.
- **build-brief** (dev): engineering brief — requirements AS STATED (quoted), decisions vs open unknowns (grill fodder), build items sized `quick fix / feature / full build` with a suggested spine route each.


Source audio stays where it is. **Never auto-commit; never overwrite existing files.**

## Recording protocol (for best speaker separation)

- **Two mics (best):** each person wears their own lav and **says their name at the very start**
  ("This is Dana" / "Rae here"). Each recorder is loudest for its wearer, so the skill aligns the two
  recorders and labels every line by who's talking. → fully attributed transcript.
- **One mic:** the wearer says their name at the start; that labels the dominant speaker, the rest is
  best-effort. Still a clean transcript, softer attribution.

## Portability (profile layer)

Three layers: a **portable engine** (`scripts/` — ASR, diarization, scoring, render), **portable
orchestration** (Steps 1–10, the agents, the two-tier model split), and **install-specific config**
(paths, private channels, named agents/skills, integrations). The third layer is data, not prose:

- `profile.schema.json` — the install contract. Optional: with no profile the defaults below run.
- `references/brain-adapters.md` — how to write into someone else's knowledge architecture (Obsidian,
  Logseq, plain folders, project-brain, git-repo-docs, Notion, none) and how far to distill into it.

**No profile = today's behavior, unchanged.** Step 0 resolves it.

## Architecture

Subagent-orchestrated so the main context stays lean. Main agent handles grouping (Step 1 verify gate),
transcription, alignment, classification, routing, and the review gate; text-heavy work goes to agents
(prompts in `agents/`):
- `transcript-cleaner.md` — one per recording/segment → clean speaker-attributed transcript. (all modes)
- `action-items-synthesizer.md` — transcripts → action-items / session-note doc, shaped by the mode's `output_shape` + `lens`.

## Model tiers (fast lane vs judgment lane)

Subagents run on two tiers — a fast breadth model for mechanical text work, a deep model for judgment. Same split the `security-audit` skill uses (Fable 5 breadth + Opus depth). Set the model when you dispatch each agent:

| Lane | Model id | Steps / agents | Why |
|---|---|---|---|
| **Fast** | `claude-fable-5` | classification triage (Step 4, reading the first ~60s), `transcript-cleaner` (Step 6 — one per recording, in parallel), cast-brief resolution (Step 5b) | Mechanical, parallel, latency-dominant. Cleaning N recordings in parallel on Fable 5 is where the run feels fast; none of it needs deep reasoning. |
| **Judgment** | `opus` | `action-items-synthesizer` (Step 7 — decodes "said vs actually want"), `client-knowledge-distiller` (Step 7 — merge + conflict), `person-enricher` (Step 7b), the execution plan (Step 8f) | Real judgment: intent, merge conflicts, one-way-door calls. Keep it deep. |

Overridable: if a transcript is long or messy and the fast cleaner drops attribution, re-run that one cleaner on the judgment tier. Defaults above are the norm; the main agent (routing, the review gate, classification decisions) stays on the session model.

## Engine & scripts

Persistent machine-local venv at `~/.cache/mlx-whisper-transcribe/venv` (NOT in the synced vault;
rebuilds on a fresh Mac). Model `mlx-community/whisper-large-v3-turbo` (kept as the default: multilingual
and robust on long files — see `references/engine-upgrades.md` for why parakeet is *not* the default and
what a single-mic-diarization upgrade would add). WAV/FLAC/OGG read directly with `soundfile`; **M4A / AAC /
MP4 / MOV auto-convert** to 16 kHz mono WAV via a local `ffmpeg` call (no cloud) — `brew install ffmpeg`
if it's missing, otherwise no manual conversion needed.

- `scripts/setup_env.sh` → ensures the base venv; prints the python path (`PY="$(bash .../setup_env.sh | tail -1)"`).
- `scripts/transcribe.py INPUT OUT_PREFIX [--language auto] [--prompt "names+jargon"] [--force]` → `.json` + `.txt` + `.segments.txt` (hallucination loops stripped). `--prompt` primes proper nouns; `--language auto` detects per file (default `en`); skips already-done files unless `--force`.
- `scripts/sample_for_grouping.py INPUT -o OUT_PREFIX [--force]` → **Step 1.** Cheap 16 kHz mono WAV (`OUT_PREFIX.sample.wav`) for grouping evidence. Does not run Whisper and does not decide groups. Files under ~6 min convert whole; longer files are start/mid/end windows. `--selftest` checks both paths.
- `scripts/diarize_two_mic.py --spine A.WAV --other B.WAV --spine-segments A.segments.txt --name-spine X --name-other Y --out A.attributed.segments.txt` → speaker-tagged segments (two recorders).
- `scripts/diarize_eval.py --segments W.segments.txt --transcript W/transcript.md --clusters W.clusters.json` → **scores** a diarization run against an already-attributed transcript and prints a verdict. Run this before trusting ANY single-mic attribution.
- `bin/meeting-loop process <recording or transcript> [--llm local|none] [--clean|--no-clean]` → the public command: transcript (plus `transcript-clean.md` when cleanup runs: default on 16 GB+ with the local model, opt-in on 8 GB; timestamps and speaker labels checked line by line, raw transcript always kept; a two-mic Profile with a sitting of exactly two audio files transcribes the first and labels each line Speaker 1/2 via `diarize_two_mic.py`, else the transcript's first line says it has no speaker labels) + notes + action-items HTML added to the Brain (append or create beside, never overwrite; a failed run leaves the Brain untouched). Last stdout line is `MEETING_LOOP_RESULT {json}`. `run-tests.sh` runs the whole local suite. `--llm local` is Private mode, in beta: a small model on this Mac drafts the action items, so check each one against its quote.
- `scripts/selftest.sh [--asr] [--diar]` → one-command engine check (compile + venv + ffmpeg convert + diarize + render; `--asr` runs real Whisper, `--diar` attempts pyannote). Run after any edit.
- `scripts/render_action_items_html.py IN.json OUT.html` → self-contained HTML action-items view + JSON export (stdlib-only).

## Capturing audio (optional front-end)

`recorder/record.sh <label> [topic]` records the Mac mic to a loop-ready 16 kHz mono WAV. See
`references/recorder.md` for usage, options, and phone capture.

## Step-by-step workflow

### Step 0 — Resolve the install profile (portability spine)
Resolution ladder, in order, first hit wins:
1. `$MEETING_LOOP_PROFILE` (explicit env var)
2. `<cwd>/profile.json`
3. a path the user names in this session

**Never load a profile from `profiles/`.** That directory holds reference instances only, and every file
in it is prefixed `EXAMPLE.` — refuse any filename matching `EXAMPLE.*`. Skill folders get copied
between machines by `import-skills`; a loose lookup there would silently hand a new install someone
else's brain root, someone else's private root, and someone else's CRM endpoint.

- **No profile found → run exactly as written below.** The defaults ARE the fallback; this
  step is additive and regresses nothing.
- **Profile found → it overrides every hardcoded path, agent, skill, and integration named in this
  file.** Load it and hold these in mind for the whole run:
  - `brain` → adapter, folder map, link dialect, merge policy, `conventions_doc` (read it — match THEIR
    house style, don't impose this vault's). Contract: `references/brain-adapters.md`.
  - `distillation.level` → L0 capture-only · L1 entity-notes · L2 atomic-concepts. Gates Steps 7/9.
    L2 without a link-capable substrate + an existing wiki + an engine **degrades to L1 — say so.**
  - `privacy` → Step 8 routing, and whether Channels B/C (Steps 5b/7b/7c) run at all. `channels.people.enabled: false`
    skips the cast brief and the enricher entirely. No identity root → Channel C never fires.
  - `owner` → who "my side" means. `mode: per-run` (company) → **ask who is running this loop before
    Step 7**, or every action item is misassigned.
  - `capture.attribution_expectation` → state it up front. `partial`/`none` means don't promise labels
    the audio can't support.
  - `execution` → Step 8f. A capability not in `integrations[]` never appears in a plan.
    `invocable_by_model: false` → emit a handoff block, never a task line. `client_facing_gate: null`
    → say plainly that nothing checked the copy.
  - `environment.hf_allowed: false` → never offer pyannote; start the diarizer ladder at `diarize_no_hf.py`.
- **Decay:** a decision older than 180 days that is about to change what happens on this run gets
  re-asked — that one question, not the whole grill.
- **Amendment:** propose profile edits mid-run the same way new meeting types are proposed — reviewed
  edit, stated plainly, applied only on approval.

Validate against `profile.schema.json`. An invalid profile is not a reason to guess: report the missing
required field, ask that one question, continue.

**Two hard refusals — these stop the run rather than warn.**

1. If `privacy.destination_shared` is true and `privacy.private_root` is missing, stop. The schema
   requires it conditionally; do not proceed with sensitive routing undefined.
2. If `privacy.private_root` resolves under `brain.root` while `privacy.vcs_autocommit` is true, stop.
   A private root inside an auto-committed tree is not private — the daemon publishes it to the remote
   and into git history, where it survives deletion. Proceed only if `privacy.private_root_exception`
   carries a dated, named justification, and say out loud which exception you are honoring.

Then state the resolved posture in one line before doing any work: profile path, adapter, distillation
level, `privacy.audience`, which channels are on, and expected attribution quality.

### Step 1 — Gather inputs, propose session groups, STOP for verify  ⚠ HARD GATE
List the audio file(s). Order chronologically by file timestamp (mtime / recording time if present),
not by the display name. Detect **two-recorder** capture (two device prefixes with matching start times)
vs single-recorder.

**iPhone Voice Memo titles are not evidence.** A phone names files from GPS or junk
(a venue, a street, "New Recording 21"). Do not
treat the filename as location, client, campus, or meeting type. Classify from the tape. Use the
filename only as an id / path.

**One file → that file is the session. Continue to Step 2.**

**More than one file → grouping is a hard gate.** Split Voice Memos of one sitting, a car ride after a
service, and a different meeting that shares a GPS name all look alike until you hear them. Grouping
from filenames is how this step fails.

1. **Inventory.** One row per file: basename, duration (`ffprobe`), mtime.
2. **Cheap samples** (not full ASR). For each file:
   `python3 <skill>/scripts/sample_for_grouping.py "<audio>" -o ~/.cache/meeting-loop/<run>/<id>`
   then, after Step 2's venv is up,
   `"$PY" <skill>/scripts/transcribe.py "<id>.sample.wav" "<id>.sample"`.
   Evidence is the sample transcript, not the filename. Skip the extract when every file already has a
   full `.segments.txt` — use the start, a mid window, and the end of those instead. Skip sample ASR
   when the owner already named the groups this session; still print the inventory.
3. **Propose numbered sessions.** A session is one sitting (one or more files). Each row: proposed
   name, files + durations, 1–2 evidence quotes from the samples, a type *hint* (not a routing decision).
   Keep a teaching/service in its own session, separate from a private debrief that shares a GPS title.
   Same street name is not the same meeting (`Oak Ave` vs `Oak Ave 2` can be two sittings).
   Worship-loop Whisper hallucinations are not evidence — `transcribe.py` strips them; ignore leftover repeats.
   **Proposed name = easy-read title + short description.** Full words. A glance has to
   answer the meeting without opening the file: event + who + what this tape is
   (`Spring Conference — Night 1 teaching (guest speaker)`, not `conf-night-1`
   and not the GPS title). Same string, kebab-cased, becomes the folder and `--topic`.
4. **STOP.** Print the proposal. Do not run Step 3 full transcribe, do not classify, do not place, do
   not launch `meeting-loop-batch`.
5. **Wait for the owner.** Confirm = "those names sound correct" / "yes" / "go" / "groups look right", plus
   any corrections he names. Apply the corrections, then continue.
6. The confirmed session list is the work-list for every later step. Launch `meeting-loop-batch` only
   with `args.groups_confirmed=true` and that list as `args.sessions`.

**Done when:** the owner has confirmed the session list in this chat. Until then, Step 1 is not done.

### Step 2 — Ensure the engine
`PY="$(bash <skill>/scripts/setup_env.sh | tail -1)"` (first run builds the venv + downloads the model).
When Step 1 needs sample ASR, run this before transcribing the sample wavs.

### Step 3 — Transcribe (first pass · optional vocab priming · resumable)
**Only after Step 1 groups are confirmed** (one file is already a session). For each file in a confirmed
session: `"$PY" <skill>/scripts/transcribe.py "<audio>" "<scratch>/<name>"`. Sanity-check one.
- **Vocab priming:** if you already know who's in the room or which client this is (the owner said so up front, or a prior capture of the *same audio*), pass `--prompt "Dana, Rae, <product names>, <jargon you use>, <client name>"` so Whisper stops mangling proper nouns and gear terms. Do **not** prime from the Voice Memo title. If names only become clear after Step 4/5, you can re-transcribe the affected file with `--prompt … --force`.
- **Resumable:** a file whose `.json/.txt/.segments.txt` all already exist is skipped automatically — a multi-file run that died partway resumes cheaply. `--force` overrides.

### Step 4 — Classify the meeting type & resolve routing  ⚠ ask-don't-assume
Classify each **confirmed session** (every file in a session shares one type), not each file.
Read `meeting-types.json`. From the first ~60s of transcript content (and later samples if needed), match against each
type's `signals`. Ignore the Voice Memo display name — it is not a signal. (Triage read can run on the fast tier, `claude-fable-5`; the confirm/route decision stays with the main agent.)
- **Confident single match** → state it and confirm: *"This reads like a {label} — going with that; say the word to switch."*
- **Ambiguous, low-confidence, or matches none** → ASK: *"What kind of meeting is this? (client / personal / creative / work — or name a new type.)"*
- **the owner names a type not in the registry** → capture it: ask its `home`, `output_shape`, whether to People-enrich, and sensitive-by-default; then **append a new entry to `meeting-types.json`** (reviewed edit). It's now a known type.

Then **resolve the routing target by asking the type's `clarify` questions** — which client slug, which
band/group/artist, which project, which brand. Never guess these.
For other modes, confirm the destination folder before writing anything.

### Step 5 — Speaker separation
- **Two recorders (best):** pick the cleaner recorder as the **spine**. Determine each recorder's owner —
  read the first ~20s of each recorder's transcript for a spoken name, else **ask the owner** the mic→person map.
  Run `diarize_two_mic.py` per segment-pair → attributed `.segments.txt`.

  **Then score it. Always.** Run `diarize_eval.py` against any transcript that already carries
  `**NAME:**` labels. If accuracy doesn't clearly beat the majority-class baseline, **throw the
  diarization away and leave the turns as `SPEAKER:`.**


  When separation fails (expect it to, on phone-on-the-table audio), fall back to **text attribution**:
  attach a name only where a spoken name, direct address, or unmistakable context makes the speaker
  certain, and label everything else `SPEAKER:`. An unattributed line is honest; a wrongly attributed
  one puts words in a real person's mouth and then propagates into their People note.

  **The actual fix is capture-side — say so to the owner rather than burning another session on audio.**
  Two recorders, one per person, each saying their name at the top → `diarize_two_mic.py`, which needs
  no model at all and no gated weights.

### Step 5a — Consent check (once per first-seen participant)
Read `privacy.consent`. On a `policy` of `all-parties-notified` or `written-consent-required`, surface it
**once** for any participant not seen in a prior run, together with `jurisdiction_note` — some
jurisdictions require every party's consent to record, not only the recorder's. Ask whether consent was
obtained; record the answer with the meeting, and flag the artifact if it wasn't. Do not nag on repeat
participants, and skip entirely on `self-recorded`. This runs whether or not Channel B is on — consent is
about the recording, not about the dossier.


### Step 6 — Clean transcripts (parallel · fast tier)
Dispatch one `transcript-cleaner` agent per recording/segment on **`claude-fable-5`** with the (attributed)
segments + metadata + known names. Launch in parallel — this is the latency sink, so the fast tier matters
most here. Each writes cleaned Markdown to scratch and returns a short summary. (If a long/messy transcript
comes back with dropped attribution, re-run that one cleaner on `opus`.)


### Step 7 — Synthesize per the mode (judgment tier)
**Resolve the owner FIRST — "my side" is meaningless until you do.** `owner.mode: single` → `owner.name`.
`per-run` → **ask who is running this loop** before dispatching. `roster` → read `owner.roster_path` and
tag every item with a named owner from it. On a multi-person install an unresolved owner misassigns
every action item, silently.

Dispatch `action-items-synthesizer` on **`opus`** with the resolved type's `output_shape` + `lens`
in its brief, so the output is shaped for THIS kind of meeting (two-sided client items vs a creative session
note vs work decisions vs a light personal note). The agent branches on `output_shape` — pass it explicitly.




### Step 8 — Place files & archive raw (⚠ transcript privacy routing — DEFAULT, do not skip)
Write the mode's privacy-clean artifacts to the resolved `home`. For **transcript.md + raw/**: a "PRIVATE"
banner is **not a control** — any sync or auto-commit (git, Dropbox, iCloud) copies the whole shared folder,
so anything sensitive in a shared folder leaks to the remote and its history. Therefore:
- **Sensitive content** (personal/pastoral/health/mental-health/family/legal — what Step 5b/7b flag), OR any
  type with `sensitive_default: true` → write transcript.md + raw/ under **`privacy.private_root`**
  (`<private_root>/<label>/<date>_<topic>/transcript.md` + `.../raw/`), and drop a `README.md` pointer in
  the shared destination. Only privacy-clean artifacts go to the shared folder. **Read the field — never
  fall back to a literal path.** Writing to a hardcoded vault path on an install that has no such folder
  creates one inside their shared tree, which is precisely the leak this step exists to prevent.
- **Genuinely benign** → transcript.md + raw/ may sit in the shared destination.
- **When unsure, treat it as sensitive.** Over-protecting costs nothing.

Session/date-prefixed; never overwrite. Folder is `<YYYY-MM-DD>_<kebab-topic>` using the
Step 1 confirmed name. Human title uses full words.
README (or the note if there is no README) opens with `**What this is:**` one sentence —
event, who, what kind of sitting — so the folder is never a mystery. Packet files stay
`notes.md` / `transcript.md` / `README.md` / `action-items.md`. Creative tapes also copy
`chords.md` (and `chords.json` into `raw/`). Report paths + the "what
changed" summary. Do **not** git-commit.

**Retention sweep.** If `privacy.retention` sets `raw_audio_days` or `transcript_days`, report which
existing artifacts are past their window. Under `enforcement: report-only` (the default) **list them and
stop — never delete.** Under `prompt-to-delete`, list them and ask; delete only what is explicitly named
back to you. A null window means keep forever and the sweep is skipped.

### Step 8g — L1: update the entity note (any mode, not just client)
**Runs when `distillation.level` is L1 or L2.** The routing target resolved in Step 4 — client, project,
band, account, person — gets its living note updated at `brain.folder_map.entity_notes`, merged per
`brain.merge_policy` (default `append-dated-block`: a new `## <date> — <topic>` section, never an edit to
prior text). This is the tier most installs sit at, and it must work for a standup, a session, or a band
practice — not only for client mode.

Every other type gets the plain merge. If `folder_map.entity_notes` is unset, ask once where the entity
note lives and offer to record the answer as a profile amendment. `distillation.cite_back` → link back
to this meeting's note.

Never overwrite. On a collision the strategy can't apply cleanly, write beside it with a `-2` suffix and
report it.

### Step 8d — Small HTML action-items view + JSON export (client mode: default)
Emit a small self-contained HTML view of the action items with a JSON Export button. Build the action-items JSON (`sections[]` — `kind:"tasks"` = checkable to-dos, `kind:"notes"` =
titled blurbs for reframes / how-to-execute), then
`python3 <skill>/scripts/render_action_items_html.py IN.json OUT.html`. Place `.json` + `.html` beside
`action-items.md`, SAME privacy routing as Step 8. Other modes: offer it, don't force it. Don't auto-commit.

### Step 8e — Creative mode: optional hand to song-loop
If it's a song/music session, offer to hand the cleaned transcript + session note + `chords.md` to the
`song-loop` skill to chart lyrics, chords and form from the audio. Opt-in.


## Conventions
- Two mics + spoken names → full attribution; otherwise best-effort with a disclaimer (cleaner bakes it in).
- Knowledge split: the meeting's own note (this meeting) · the living per-entity note where one exists (client-profile.md / person note) · a concept wiki if you keep one (reusable concepts) · a CRM if configured (client tasks). Don't duplicate across them.
- Markdown deliverables; vault notes get frontmatter per `CLAUDE.md`. Raw → `<meeting>/raw/`, never into the wiki.
- Ask before routing. Propose the type, confirm the destination. Clarity beats a clever guess.
- Several recordings: propose session groups from samples, stop, continue only after the owner confirms (Step 1). Filename grouping is the failure mode. `meeting-loop-batch` needs `args.groups_confirmed=true`.
- **Names are for humans.** Session title, folder, and `--topic` are the same easy-read string: event + who + a short description of what the sitting is, full words, no GPS junk, no abbreviations. `_1`/`_2` is not a description — name the part (worship, teaching, car, walk). README opens with `**What this is:**` one sentence.
