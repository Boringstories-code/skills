#!/usr/bin/env python3
"""meeting_loop.py — the `meeting-loop` command (run it through bin/meeting-loop).

    meeting-loop process <recording...> [--type <meeting type>]
        [--entity <note> | --no-entity] [--clean | --no-clean]
        [--llm local|none|agent] [--agent-items PATH]
    meeting-loop setup [--brain PATH] [--mics one|two] [--types id,id,...] [--yes]
    meeting-loop doctor
    meeting-loop record [--stop]
    meeting-loop find <folder>
    meeting-loop transcribe <recording> [--out PATH]
    meeting-loop render <items.json> [--out PATH]
    meeting-loop write <note> (--text TEXT | --file PATH)
    meeting-loop version
    meeting-loop uninstall [--yes]

find/transcribe/render/write are the smaller, single-purpose commands behind the
MCP server's tools (Skills/meeting-loop/mcp/server.py) and anything else that
wants one piece of the pipeline on its own, not the whole `process` run.

process: load transcript(s) -> optional cleanup -> synthesize -> quote check -> render
-> write to the Brain. Cleanup (on by default on 16 GB+ Macs with the local model, opt-in
on 8 GB) writes transcript-clean.md beside the raw transcript, which is always kept;
synthesis and the quote check read the raw lines. Several recordings close in time are
proposed as one sitting and confirmed
(interactively, or by the flags below) before anything is written. Every action
item, whatever synthesized it, passes through quote_check() before it can reach
the Brain: a dropped quote never becomes a task, and an owner is only ever named
when the transcript actually names one.
Every run ends with one line, `MEETING_LOOP_RESULT {json}`, listing the files it
produced; on failure that line says ok=false, the exit code is non-zero and the
Brain is untouched. `process` with no Profile runs `setup` first (non-interactively
when stdin isn't a terminal, so scripted/CI runs still get a usable default).
Stdlib only.

Ask, don't assume: grouping, meeting type, and the entity note are each
confirmed, not guessed. `--type` and `--entity`/`--no-entity` answer those
questions for scripts and agents. With no terminal attached and no flag, a
question that can't be answered safely either takes its documented default
(meeting type) or is skipped outright (entity note, grouping) — never guessed.
"""
import argparse
import bisect
import datetime
import itertools
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import local_model  # noqa: E402
from brain_writer import BrainWriteError, write_to_brain  # noqa: E402
from render_action_items_html import render_html  # noqa: E402
import ml_profile as profile_mod  # noqa: E402

RESULT = "MEETING_LOOP_RESULT"
DOCTOR_RESULT = "MEETING_LOOP_DOCTOR_RESULT"
DEFAULT_VERSION_URL = ""  # no update server ships; set MEETING_LOOP_VERSION_URL to turn the check on
TRANSCRIPT_EXTS = {".txt", ".md"}
AUDIO_EXTS = {".wav", ".flac", ".m4a", ".mp3"}
RECORDING_EXTS = AUDIO_EXTS | TRANSCRIPT_EXTS
SEGMENT = re.compile(r"^\[(?P<start>[\d:.]+)\s*->\s*[\d:.]+\]\s*(?P<text>.*)$")
SPEAKER = re.compile(r"^(?P<speaker>[^:\[\]]{1,40}):\s+(?P<text>.+)$")
# --llm none: a line that sounds like someone agreeing to do something.
COMMITMENT = re.compile(
    r"\b(i'll|i will|we'll|we will|let's|can you|could you|need to|needs to|going to|follow up|action item)\b",
    re.I)
# Private mode (ticket 11): the lines the local model is asked about. Wide on purpose: the
# model decides which tagged lines are real to-dos, and a to-do on an untagged line is never found.
CUE = re.compile(
    r"\b(i['’]ll|i will|we['’]ll|we will|let me|lemme|let['’]s|going to|gonna|i want to|we want to|wanna|"
    r"i can|we can|you can|can you|could you|would you|will you|please|i want you to|"
    r"need to|needs to|have to|has to|got to|gotta|should|must|supposed to|make sure|"
    r"don['’]t forget|remember to|follow up|action item|next steps?|to-?do|"
    r"send|email|text|call|draft|schedule|book|set up|figure out|look into|check|finish|build|update|share|"
    r"today|tonight|tomorrow|this week|next week|later|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", re.I)
# Quote check / owner rule (ticket 02): a line naming its own speaker as the doer,
# versus a line asking "you" to do it, where the owner is whoever answers.
FIRST_PERSON = re.compile(r"\b(i'll|i will|i'm going to|i am going to|i can)\b", re.I)
REQUEST = re.compile(r"\b(can you|could you|would you|will you)\b", re.I)


def _normalize(text):
    return re.sub(r"\s+", " ", text).strip().casefold()


def _find_line_index(quote, lines):
    """-> index of the transcript line where quote starts, normalized; None if none.
    A quote may run across lines (a raw transcript breaks sentences into fragments)."""
    norms = [_normalize(l["text"]) for l in lines]
    at = " ".join(norms).find(_normalize(quote))
    if at < 0:
        return None
    starts = [0, *itertools.accumulate(len(n) + 1 for n in norms)][:-1]
    return bisect.bisect_right(starts, at) - 1


def _owner_for(idx, lines):
    """-> the speaker who named themselves (or was named) as the doer of lines[idx], else None."""
    line = lines[idx]
    if line["speaker"] and FIRST_PERSON.search(line["text"]):
        return line["speaker"]
    if REQUEST.search(line["text"]):
        for j in (idx + 1, idx - 1):
            if 0 <= j < len(lines):
                neighbor = lines[j]
                if neighbor["speaker"] and neighbor["speaker"] != line["speaker"] and FIRST_PERSON.search(neighbor["text"]):
                    return neighbor["speaker"]
    return None


def quote_check(items, lines):
    """The deterministic check every action-item source passes through.

    Drops any item whose quote isn't found in the transcript (after whitespace/case
    normalization) and sets owner only when the quoted line, or a neighbor answering
    it, names one -- otherwise "unassigned". -> (kept_items, dropped_count).
    """
    haystack = _normalize(" ".join(l["text"] for l in lines))
    kept = []
    dropped = 0
    for it in items:
        quote = it.get("quote") or ""
        if not quote.strip() or _normalize(quote) not in haystack:
            dropped += 1
            continue
        idx = it["at"] if isinstance(it.get("at"), int) else _find_line_index(quote, lines)
        it.setdefault("ts", lines[idx]["ts"] if idx is not None else None)
        it.setdefault("speaker", lines[idx]["speaker"] if idx is not None else None)
        it["owner"] = (_owner_for(idx, lines) or "unassigned") if idx is not None else "unassigned"
        kept.append(it)
    return kept, dropped

DEFAULT_TYPE = "work"  # the registry's generic/unknown catch-all (meeting-types.json)
GROUP_GAP = datetime.timedelta(minutes=30)  # beyond this, recordings propose as separate sittings


class RunError(Exception):
    """A plain-language reason the run stopped."""


DEFAULT_BRAIN = "~/MeetingLoop/Brain"
MEETING_TYPES_PATH = HERE.parent / "meeting-types.json"


def known_type_ids():
    try:
        return [t["id"] for t in json.loads(MEETING_TYPES_PATH.read_text())["types"]]
    except (OSError, KeyError, json.JSONDecodeError):
        return ["client", "personal", "creative", "dev", "work"]


def _ask(prompt, default, interactive):
    if not interactive:
        print(f"[setup] {prompt} using default: {default}")
        return default
    answer = input(f"{prompt} [{default}]: ").strip()
    return answer or default


def run_setup(brain=None, mics=None, types=None, interactive=None):
    """Three questions -> a schema-valid Profile, written to disk. -> path.

    `interactive` defaults to whether stdin is a terminal, so a scripted or
    CI run (stdin not a tty) gets the recommended defaults instead of hanging
    on input(). Any answer passed explicitly skips its question.
    """
    if interactive is None:
        interactive = sys.stdin.isatty()
    display_name = os.environ.get("USER") or "You"

    if brain is None:
        brain = _ask("Where should your Brain (notes) live?", DEFAULT_BRAIN, interactive)
    if profile_mod.is_protected(brain):
        print(f"meeting-loop: {profile_mod.PROTECTED_WARNING}")

    if mics is None:
        mics = _ask("One mic, or two (one per speaker)?", "one", interactive)
    if mics not in ("one", "two"):
        raise RunError("mics must be 'one' or 'two'")

    available = known_type_ids()
    if types is None:
        default_types = ",".join(available)
        answer = _ask(f"Which meeting types do you record? ({', '.join(available)})",
                       default_types, interactive)
        types = [t.strip() for t in answer.split(",") if t.strip()]
    unknown = [t for t in types if t not in available]
    if unknown:
        raise RunError(f"unknown meeting type(s): {', '.join(unknown)} (known: {', '.join(available)})")

    data = profile_mod.default_profile(brain, mics, types, display_name)
    path = profile_mod.write_profile(data)
    print(f"[setup] wrote Profile to {path}")
    return path


def load_profile_migrating(path=None):
    """profile_mod.load_profile, but a migration is written back to disk
    immediately so every later read sees the current version too."""
    path = path or profile_mod.profile_path()
    data, migrated = profile_mod.load_profile(path)
    if migrated:
        profile_mod.write_profile(data, path)
        print(f"[setup] migrated the Profile at {path} to version {profile_mod.CURRENT_VERSION}")
    return data


def load_or_setup_profile():
    """The Profile every other command reads. Creates one via `setup` the first time
    there isn't one: the three questions at a terminal, recommended defaults otherwise."""
    path = profile_mod.profile_path()
    if not path.exists():
        print("[setup] no Profile yet; running setup first", flush=True)
        run_setup()
    try:
        return load_profile_migrating(path)
    except profile_mod.ProfileError as e:
        raise RunError(str(e))


def brain_root(profile=None):
    if profile is None:
        profile = load_or_setup_profile()
    return Path(profile["brain"]["root"]).expanduser()


def ask(prompt):
    """Print prompt, read one line from stdin. None when there's nothing to read
    (no terminal, closed/empty stdin) or the answer was blank — never guesses."""
    print(prompt, flush=True)
    try:
        line = sys.stdin.readline()
    except (OSError, ValueError):
        return None
    line = line.strip()
    return line or None


def meeting_type_ids():
    data = json.loads((HERE.parent / "meeting-types.json").read_text())
    return [t["id"] for t in data["types"]]


def confirm_type(cli_type):
    """The meeting type, confirmed before output is shaped. A flag answers the
    question outright; otherwise ask, and fall back to the registry's documented
    generic default only when there is truly no way to ask."""
    ids = meeting_type_ids()
    if cli_type:
        if cli_type not in ids:
            raise RunError(f"unknown meeting type {cli_type!r}; known types: {', '.join(ids)}")
        return cli_type
    answer = ask(f"[process] which meeting type is this? ({', '.join(ids)})")
    if answer is None:
        print(f"[process] no terminal attached and no --type given; defaulting to {DEFAULT_TYPE!r}", flush=True)
        return DEFAULT_TYPE
    if answer not in ids:
        raise RunError(f"unknown meeting type {answer!r}; known types: {', '.join(ids)}")
    return answer


def confirm_entity(args):
    """The entity note to grow, confirmed rather than guessed. With no flag and
    no answer, skip the note outright and say so."""
    if args.no_entity:
        print("[process] --no-entity: skipping the entity note", flush=True)
        return None
    if args.entity:
        return args.entity
    answer = ask("[process] which entity note does this sitting belong to? (blank to skip)")
    if not answer:
        print("[process] no entity note named; skipping the entity note", flush=True)
        return None
    return answer


def propose_groups(sources):
    """sources sorted by mtime. -> list of groups (list of Path), split wherever
    the gap to the next recording exceeds GROUP_GAP."""
    groups = [[sources[0]]]
    for prev, nxt in zip(sources, sources[1:]):
        gap = (datetime.datetime.fromtimestamp(nxt.stat().st_mtime)
               - datetime.datetime.fromtimestamp(prev.stat().st_mtime))
        if gap > GROUP_GAP:
            groups.append([nxt])
        else:
            groups[-1].append(nxt)
    return groups


def confirm_groups(sources, accept=False):
    """Several recordings -> a proposed grouping into sittings, confirmed before
    anything is processed. Nothing to confirm when every recording already
    proposes as its own sitting. With no answer (or "no"), fall back to
    processing each recording separately — the one choice that assumes nothing."""
    groups = propose_groups(sources)
    if all(len(g) == 1 for g in groups):
        return groups
    print("[process] proposed sitting groups:", flush=True)
    for i, g in enumerate(groups, 1):
        print(f"  {i}. " + ", ".join(p.name for p in g), flush=True)
    if accept:
        print("[process] --yes: using the proposed groups", flush=True)
        return groups
    answer = ask("[process] do these groups look right? [y/n] (no answer treats each recording separately)")
    if answer and answer.lower().startswith("y"):
        return groups
    print("[process] processing each recording as its own sitting", flush=True)
    return [[s] for s in sources]


def whisper_model_cached():
    """True when the engine's Whisper model is already in the Hugging Face cache."""
    model = os.environ.get("CML_WHISPER_MODEL", "mlx-community/whisper-large-v3-turbo")
    hub = os.environ.get("HF_HUB_CACHE") or Path(os.environ.get("HF_HOME", Path.home() / ".cache/huggingface")) / "hub"
    return any((Path(hub) / f"models--{model.replace('/', '--')}" / "snapshots").glob("*/config.json"))


def engine_python():
    """-> the engine venv's python (numpy, Whisper); this script runs under plain python3."""
    env_setup = subprocess.run(["bash", str(HERE / "setup_env.sh")], capture_output=True, text=True)
    if env_setup.returncode != 0:
        raise RunError("the transcription engine isn't set up: " + env_setup.stderr.strip()[-300:])
    return env_setup.stdout.strip().splitlines()[-1]


def transcribe(recording, workdir):
    """Recording -> segments file, via the engine's Whisper script."""
    python = engine_python()
    out = Path(workdir) / "t"
    env = dict(os.environ, HF_HUB_DISABLE_TELEMETRY="1")
    if whisper_model_cached():
        env["HF_HUB_OFFLINE"] = "1"  # Private mode: no network at run time once the model is local
    else:
        print("[process] first audio run: downloading the Whisper model once (~1.6 GB); "
              "every run after this is offline", flush=True)
    if subprocess.run([python, str(HERE / "transcribe.py"), str(recording), str(out)], env=env).returncode != 0:
        raise RunError(f"transcription failed on {recording}")
    return out.with_suffix(".segments.txt")


def label_speakers(spine, other, segments, workdir):
    """Two-mic sitting: the spine's segments -> the same lines, each tagged with whichever
    mic was louder at that moment (scripts/diarize_two_mic.py, run on the engine python)."""
    out = Path(workdir) / "t.attributed.segments.txt"
    # ponytail: neutral names; the Profile holds no per-mic names and the audio is the only
    # thing that could establish them (pack SKILL "Two mics").
    cmd = [engine_python(), str(HERE / "diarize_two_mic.py"), "--spine", str(spine), "--other", str(other),
           "--spine-segments", str(segments), "--name-spine", "Speaker 1", "--name-other", "Speaker 2",
           "--out", str(out)]
    if subprocess.run(cmd).returncode != 0:
        raise RunError(f"speaker labels failed on {spine.name} + {other.name}")
    return out


def load_transcript_text(text):
    """Transcript text -> [{line, ts, speaker, text}] for every non-empty line."""
    lines = []
    for raw in text.splitlines():
        if not raw.strip():
            continue
        seg = SEGMENT.match(raw.strip())
        ts, words = (seg["start"], seg["text"]) if seg else (None, raw.strip())
        who = SPEAKER.match(words)
        speaker, words = (who["speaker"], who["text"]) if who else (None, words)
        lines.append({"line": raw.rstrip(), "ts": ts, "speaker": speaker, "text": words})
    return lines


def load_transcript(path):
    """Transcript file -> [{line, ts, speaker, text}] for every non-empty line."""
    lines = load_transcript_text(Path(path).read_text())
    if not lines:
        raise RunError(f"{path} has no transcript lines")
    return lines


def _label(l):
    """The part of a transcript line before its words ('[a -> b] Speaker:'), whitespace-normalized."""
    s = l["line"].strip()
    return re.sub(r"\s+", " ", s[:len(s) - len(l["text"])]).strip()


def align_cleaned(lines, reply):
    """Raw lines + the model's cleaned-up version of them -> (cleaned lines, fallbacks).

    The invariant is enforced here, not trusted to the model: a raw line takes the
    model's words only from a reply line (searched forward, in order) whose timestamp
    and speaker label are the same; the line is rebuilt from the raw label plus those
    words. Anything else -- a moved timestamp, a swapped or invented speaker, a dropped
    line, a line with no label to anchor it -- keeps the raw line and counts a fallback.
    """
    reply_lines = load_transcript_text(reply)
    out, fallbacks, j = [], 0, 0
    for raw in lines:
        label = _label(raw)
        hit = next((k for k in range(j, len(reply_lines))
                    if label and _label(reply_lines[k]) == label and reply_lines[k]["text"].strip()), None)
        if hit is None:
            out.append(dict(raw))
            fallbacks += 1
            continue
        j = hit + 1
        words = reply_lines[hit]["text"].strip()
        head = raw["line"][:len(raw["line"]) - len(raw["text"])]
        out.append(dict(raw, line=head + words, text=words))
    return out, fallbacks


TURN_CHARS = 300  # a raw transcript's fragments are joined into turns up to this long
CHUNK_CHARS = 8000  # transcript text per summary call (about 2k tokens)
SUMMARY_PROMPT = """You read one part of a meeting transcript. Reply with JSON only, no other text:
{"summary": "..."} in one to three plain sentences on what this part covered and decided."""
MOMENT_BEFORE, MOMENT_AFTER = 500, 250  # transcript characters shown around a CUE line
# Is the [[bracketed]] line a to-do? The model's yes-vs-no log-odds, against a bar: a bar can be
# set, where a free-text yes/no from Qwen3-8B said yes to 98% of cue lines. Set per model on 78
# hand-sorted cue lines from three real sittings. Qwen3-8B: AUC 0.85, at -7.0 it keeps 82% of real
# to-dos and 29% of the rest. Qwen3-4B leans yes and sorts worse: AUC 0.71, at +11.6 it keeps 85%
# and 53%.
ODDS_PROMPT = (  # one paragraph, word for word as the bars were set on: a line break moves the odds
    "You check one moment in a meeting transcript: the words in [[double brackets]]. Is someone taking on a "
    "to-do there: something to do after this moment that they say they will do, are asked to do, or the group "
    "settles on? Not a to-do: explaining how something works, describing a process or a demo, doing it right "
    "now on the call, already done, an opinion, a maybe nobody takes up, small talk. Answer yes or no.")
TODO_ODDS = {False: -7.0, True: 11.6}  # keyed by low_ram (False: Qwen3-8B, True: Qwen3-4B)
# Shown above Private mode's action items (ticket 11): it ships as a beta. Judged on four real
# sittings it caught 73-78% of the to-dos a careful reader listed (16 GB; about 71% on 8 GB),
# and over half of each list was repeats or lines that weren't to-dos.
BETA_NOTE = ("Private mode is in beta. A small model on this Mac wrote this list. It catches most to-dos, "
             "but expect repeats and lines that aren't to-dos. Check each one against its quote.")
TASK_PROMPT = """You read one moment in a meeting transcript. The words in [[double brackets]] are a to-do
someone took on. Write that to-do as one short instruction, verb first. Say what the bracketed words
say; use the nearby lines only to tell what "it", "this" or "that" means. Add a deadline only if the
transcript states one. Reply with the instruction only, without brackets."""
MERGE_PROMPT = """You combine summaries of consecutive parts of one meeting into one summary.
Reply with JSON only, no other text: {"summary": "..."} in two to four plain sentences."""


def _clock(secs):
    secs = int(round(secs))
    return f"{secs // 60}m {secs % 60:02d}s" if secs >= 60 else f"{secs}s"


class LocalModel:
    """The on-device model for one run: loaded on first use, then shared by cleanup and
    synthesis so it loads once. A missing engine or model stops the run (RunError)."""

    def __init__(self, choice):
        self.choice, self._session = choice, None

    def _start(self):
        if self._session is None:
            print(f"[local] loading {self.choice['model']} (on this Mac, network off)", flush=True)
            self._session = local_model.Session(self.choice["model"])
            print(f"[local] model ready in {_clock(self._session.loaded)}", flush=True)
        return self._session

    def ask(self, system, user, max_tokens):
        try:
            return self._start().ask(system, user, max_tokens=max_tokens)
        except local_model.ModelError as e:
            raise RunError(str(e))

    def odds(self, system, user):
        try:
            return self._start().odds(system, user)
        except local_model.ModelError as e:
            raise RunError(str(e))

    def close(self):
        if self._session is not None:
            self._session.close()


def _run_parts(tag, users, call):
    """call(user) -> (result, seconds) once per part, printing progress with a time
    estimate. -> [result]."""
    replies, done, spent, total = [], 0, 0.0, sum(len(u) for u in users)
    for n, user in enumerate(users, 1):
        text, secs = call(user)
        replies.append(text)
        done, spent = done + len(user), spent + secs
        eta = f", about {_clock(spent / done * (total - done))} left" if n < len(users) else ""
        if n % 10 == 0 or n == len(users):
            print(f"[{tag}] part {n}/{len(users)} done in {_clock(secs)}{eta}", flush=True)
    return replies


def _turns(lines, max_chars=TURN_CHARS):
    """Consecutive lines from one speaker -> one "Speaker: text" turn, so the sentence
    fragments of a raw transcript reach the model whole."""
    turns = []
    for l in lines:
        if turns and turns[-1][0] == l["speaker"] and len(turns[-1][1]) + len(l["text"]) < max_chars:
            turns[-1][1] += " " + l["text"]
        else:
            turns.append([l["speaker"], l["text"]])
    return [f"{who}: {text}" if who else text for who, text in turns]


def _moment(lines, i):
    """The words around lines[i] as speaker turns, with lines[i] in [[double brackets]]."""
    a, used = i, 0
    while a > 0 and used + len(lines[a - 1]["text"]) <= MOMENT_BEFORE:
        a, used = a - 1, used + len(lines[a - 1]["text"])
    b, used = i + 1, 0
    while b < len(lines) and used + len(lines[b]["text"]) <= MOMENT_AFTER:
        b, used = b + 1, used + len(lines[b]["text"])
    window = [dict(l, text=f"[[{l['text']}]]") if j == i else l for j, l in enumerate(lines[a:b], a)]
    return "\n".join(_turns(window, max_chars=10**6))


def check_tagged(lines, model):
    """Private mode's action items: the model scores each CUE line, with the words around it,
    and writes a task for the ones at or over its model's TODO_ODDS bar. The quote is that line's own words,
    so the model never copies one. -> [{task, quote, at}]."""
    tagged = [i for i, l in enumerate(lines) if CUE.search(l["text"])]
    print(f"[local] checking {len(tagged)} line(s) that may be action items", flush=True)
    moments = {i: _moment(lines, i) for i in tagged}
    odds = _run_parts("check", [moments[i] for i in tagged], lambda u: model.odds(ODDS_PROMPT, u))
    bar = TODO_ODDS[model.choice["low_ram"]]
    kept = [i for i, o in zip(tagged, odds) if o >= bar]
    tasks = _run_parts("task", [moments[i] for i in kept], lambda u: model.ask(TASK_PROMPT, u, 60))
    tidy = lambda t: t.replace("[[", "").replace("]]", "").strip().strip("\"'“”").strip()
    return [{"task": tidy(t) or lines[i]["text"], "quote": lines[i]["text"], "at": i} for i, t in zip(kept, tasks)]


def synthesize_local(lines, model):
    """Private mode: the on-device model summarizes the transcript in parts, then judges
    each CUE line as an action item or not. Prints progress with a time estimate."""
    texts = _turns(lines)
    spans = local_model.chunks(texts, CHUNK_CHARS)
    users = [f"Transcript part {n} of {len(spans)}:\n" + "\n".join(texts[a:b]) for n, (a, b) in enumerate(spans, 1)]
    print(f"[local] reading {len(users)} part(s) for the summary", flush=True)
    replies = [local_model.read_json(t) for t in _run_parts("local", users, lambda u: model.ask(SUMMARY_PROMPT, u, 300))]
    summaries = [r["summary"].strip() for r in replies
                 if r and isinstance(r.get("summary"), str) and r["summary"].strip()]
    items = check_tagged(lines, model)
    unreadable = sum(r is None for r in replies)
    summary = " ".join(summaries) or None
    if len(summaries) > 1:
        print(f"[local] combining {len(summaries)} part summaries", flush=True)
        parts = "\n".join(f"Part {n}: {s}" for n, s in enumerate(summaries, 1))
        combined = (local_model.read_json(model.ask(MERGE_PROMPT, parts, max_tokens=400)[0]) or {}).get("summary")
        summary = combined.strip() if isinstance(combined, str) and combined.strip() else summary
    if unreadable:
        print(f"[local] {unreadable} reply(ies) couldn't be read; skipped", flush=True)
    return {"summary": summary, "action_items": items,
            "note": BETA_NOTE + (" " + local_model.LOW_RAM_NOTE if model.choice["low_ram"] else "")}


# Cleanup (ticket 04): the model rewrites wording only; align_cleaned() enforces that every
# timestamp and speaker label comes back unchanged, line for line.
CLEAN_CHUNK_CHARS = 3000  # the model writes every line back, so parts are smaller than CHUNK_CHARS
CLEAN_PROMPT = """You tidy up one part of a meeting transcript. Each line starts with a timestamp in
brackets, often followed by a speaker name and a colon. Reply with the same lines, in the same order,
one output line per input line, and nothing else.
Copy each line's timestamp and speaker label exactly, character for character.
After the label, rewrite only the words: drop filler (um, uh, you know), false starts and stutters,
fix obvious mis-hearings, punctuation and capitalization. Keep everything the speaker meant and keep
their wording otherwise. Never summarize, merge, split, add or drop a line."""
# Measured with the network off (tests/slow_private_mode.py, 16 GB Apple silicon Mac):
# seconds of cleanup per 1000 transcript characters (the model writes every line back,
# timestamps included), and the one-time model load. An 8 GB Mac may run slower.
CLEAN_SECS_PER_KCHAR = {False: 20.0, True: 13.0}  # keyed by low_ram (False: Qwen3-8B, True: Qwen3-4B)
MODEL_LOAD_SECS = 3.0


def cleanup_estimate(chars, low_ram):
    """-> seconds cleanup would add for a transcript of this many characters."""
    return MODEL_LOAD_SECS + chars / 1000 * CLEAN_SECS_PER_KCHAR[low_ram]


def want_cleanup(args, choice, lines):
    """--clean / --no-clean decide outright. Otherwise: on with the local model on a 16 GB+
    Mac; on an 8 GB Mac off, with the extra time shown -- asked only at a terminal, never
    otherwise. The first answer is kept for the rest of the run."""
    if args.clean is not None:
        if not args.clean:
            print("[clean] off", flush=True)
        return args.clean
    if choice["low_ram"]:
        extra = _clock(cleanup_estimate(sum(len(l["line"]) + 1 for l in lines), True))
        if sys.stdin.isatty():
            answer = ask(f"[clean] clean up the transcript wording too? It adds about {extra} on this Mac. [y/N]")
            args.clean = bool(answer and answer.lower().startswith("y"))
            return args.clean
        print(f"[clean] skipped on this Mac (under 16 GB of memory); cleaning up the wording would add "
              f"about {extra}. Run again with --clean to include it.", flush=True)
        return False
    if args.llm != "local":
        print(f"[clean] off: --llm {args.llm} loads no model; add --clean to clean up the wording", flush=True)
        return False
    return True


def clean_lines(lines, model):
    """-> (cleaned lines, fallbacks): the model's wording, every label checked against the raw line."""
    texts = [l["line"].strip() for l in lines]
    spans = local_model.chunks(texts, CLEAN_CHUNK_CHARS)
    print(f"[clean] cleaning up the wording in {len(spans)} part(s)", flush=True)
    replies = _run_parts("clean", ["\n".join(texts[a:b]) for a, b in spans],  # timestamps run about
                         lambda u: model.ask(CLEAN_PROMPT, u, len(u) + 256))  # a token per character
    cleaned, fallbacks = [], 0
    for (a, b), reply in zip(spans, replies):
        got, fb = align_cleaned(lines[a:b], re.sub(r"<think>.*?(</think>|$)", "", reply, flags=re.S))
        cleaned += got
        fallbacks += fb
    print(f"[clean] {len(lines)} lines; {fallbacks} kept as heard (timestamp or speaker label didn't match)",
          flush=True)
    return cleaned, fallbacks


def synthesize(lines, llm, agent_items=None, model=None):
    """-> {"summary": str or None, "action_items": [{task, quote, ts, speaker}]}

    Owner is not set here -- quote_check() is the one place that names an owner or
    falls back to "unassigned", for every source below alike.
    """
    if llm == "local":
        return synthesize_local(lines, model)
    if llm == "agent":
        # Agent handoff: the caller already did the thinking. The skill pack hands over
        # {"summary": str, "action_items": [{task, quote, owner?}]}; a bare list of items
        # is accepted too. quote_check still gates every item.
        try:
            handoff = json.loads(Path(agent_items).read_text())
        except (OSError, json.JSONDecodeError) as e:
            raise RunError(f"couldn't read agent items from {agent_items}: {e}")
        if isinstance(handoff, list):
            handoff = {"action_items": handoff}
        items = handoff.get("action_items") if isinstance(handoff, dict) else None
        if not isinstance(items, list) or not all(isinstance(i, dict) for i in items):
            raise RunError(f"{agent_items} needs an action_items list of {{task, quote}} objects")
        return {"summary": handoff.get("summary") or None, "action_items": items}
    items = [{"task": l["text"], "quote": l["text"], "ts": l["ts"], "speaker": l["speaker"]}
             for l in lines if COMMITMENT.search(l["text"])]
    return {"summary": None, "action_items": items}


def sitting_folder(anchor, now):
    date = datetime.date.fromtimestamp(anchor.stat().st_mtime).isoformat()
    name = anchor.name.split(".")[0]
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "sitting"
    return f"Meeting Loop/{date}-{slug}", date, slug


def sitting_outputs(entries, synth, anchor, now, mtype, llm, no_labels=None):
    """entries: [(source, raw lines, cleaned lines or None)] for one sitting, chronological;
    synth: the sitting's one synthesis (quote-checked against every recording in it);
    no_labels: the plain line that tops the transcript when it has no speaker labels.
    -> [(path relative to the Brain, text)]."""
    folder, date, slug = sitting_folder(anchor, now)
    stamp = now.strftime("%Y-%m-%d %H:%M")
    all_items = synth["action_items"]
    any_summary = synth["summary"]
    note = synth.get("note")  # 8 GB Macs

    def transcript_md(pick):
        return (f"{no_labels}\n\n" if no_labels else "") + "\n\n".join(f"## {stamp} · {source.name}\n\n" + "\n".join(l["line"] for l in pick(lines, cleaned))
                           for source, lines, cleaned in entries) + "\n"

    transcript = transcript_md(lambda lines, cleaned: lines)
    # Cleanup (ticket 04) is written beside the raw transcript, never over it; a recording
    # in the sitting that wasn't cleaned contributes its raw lines.
    cleaned = (transcript_md(lambda lines, cleaned: cleaned or lines)
               if any(c for _, _, c in entries) else None)

    notes = [f"## {stamp} · {anchor.name}", ""] + ([f"> {note}", ""] if note else []) + [
             f"**Type:** {mtype}", "",
             f"**Summary:** {any_summary or ('none (--llm none writes no summary)' if llm == 'none' else 'none given')}", "",
             "### Action items", ""]
    for it in all_items:
        said = " · ".join(x for x in (it["speaker"], it["ts"]) if x)
        notes += [f"- [ ] {it['task']} (owner: {it['owner']})", f"  > \"{it['quote']}\"" + (f" ({said})" if said else "")]
    if not all_items:
        notes.append("- none found")

    view = render_html({
        "title": "Action items", "subtitle": anchor.name, "date": date, "meeting": slug,
        "sections": [{
            "heading": "Action items", "kind": "tasks",
            "note": note or ("Keyword matches only (--llm none). Check each one against the transcript."
                             if llm == "none" else ""),
            "items": [{"task": it["task"], "detail": f"\"{it['quote']}\"  owner: {it['owner']}"} for it in all_items],
        }],
    })
    return [(f"{folder}/transcript.md", transcript)] + (
        [(f"{folder}/transcript-clean.md", cleaned)] if cleaned else []) + [
            (f"{folder}/notes.md", "\n".join(notes) + "\n"),
            (f"{folder}/action-items.html", view)]


def entity_note_write(entity, entries, synth, mtype, now, folder, notes_dir):
    """-> one (path relative to the Brain, text) write: a dated block appended
    to the named entity note (brain_writer never overwrites prior content).
    notes_dir is the Profile's brain.folder_map.entity_notes (default Entities/)."""
    slug = re.sub(r"[^a-z0-9]+", "-", entity.lower()).strip("-") or "entity"
    date = now.strftime("%Y-%m-%d")
    names = ", ".join(source.name for source, _, _ in entries)
    total = len(synth["action_items"])
    body = (f"## {date} — {names}\n\n"
            f"Type: {mtype}. {total} action item(s) from this sitting. "
            f"See `{folder}/notes.md`.\n")
    return (f"{notes_dir.rstrip('/')}/{slug}.md", body)


def process(args):
    profile = load_or_setup_profile()
    sources = [Path(r) for r in args.recordings]
    for s in sources:
        if not s.is_file():
            raise RunError(f"no such file: {s}")
    sources.sort(key=lambda p: p.stat().st_mtime)

    if args.sitting or len(sources) == 1:
        groups = [sources]
    else:
        groups = confirm_groups(sources, accept=args.yes)
    mtype = confirm_type(args.type)
    entity = confirm_entity(args)
    now = datetime.datetime.now()

    all_writes = []
    total_kept, total_dropped, note = 0, 0, None
    cleanup = {"ran": False}
    notes_dir = (profile.get("brain", {}).get("folder_map") or {}).get("entity_notes") or "Entities/"
    two_mic = (profile.get("capture") or {}).get("method") == "two-mic"
    model = LocalModel(local_model.choose_model())
    try:
        for group in groups:
            if two_mic and len(group) == 2 and all(s.suffix.lower() in AUDIO_EXTS for s in group):
                # The two mics of one conversation: one transcript, from the spine (first by mtime).
                entries = [process_recording(group[0], args, model, cleanup, other=group[1])]
            else:
                entries = [process_recording(source, args, model, cleanup) for source in group]
            no_labels = None
            if not any(l["speaker"] for _, raw, _ in entries for l in raw):
                no_labels = ("No speaker labels: the Profile says two mics, but this sitting isn't exactly "
                             "two audio recordings." if two_mic else "No speaker labels: recorded with one mic.")
                print(f"[process] {no_labels}", flush=True)
            # One synthesis + quote check per sitting: an item may quote any recording in it.
            lines = [l for _, raw, _ in entries for l in raw]
            synth = synthesize(lines, args.llm, args.agent_items, model)
            kept_items, dropped = quote_check(synth["action_items"], lines)
            synth.update(action_items=kept_items, dropped=dropped)
            print(f"[process] sitting: {len(kept_items)} action items kept, {dropped} dropped by quote check",
                  flush=True)
            if synth.get("note"):
                print(f"[process] note: {synth['note']}", flush=True)
            total_kept += len(kept_items)
            total_dropped += dropped
            note = synth.get("note") or note
            anchor = group[0]
            folder, _, _ = sitting_folder(anchor, now)
            all_writes += sitting_outputs(entries, synth, anchor, now, mtype, args.llm, no_labels)
            if entity:
                all_writes.append(entity_note_write(entity, entries, synth, mtype, now, folder, notes_dir))
    finally:
        model.close()
    files = write_to_brain(brain_root(profile), all_writes)
    return files, total_kept, total_dropped, note, cleanup


def process_recording(source, args, model, cleanup, other=None):
    """One recording -> (source, raw lines, cleaned lines or None). Synthesis and the quote
    check run per sitting in process() and always read the raw lines, so a quote is checked
    against what was actually heard, not the tidied wording. other: the second mic of a
    two-mic sitting; only source is transcribed, other decides who spoke each line."""
    print(f"[process] {source.name}" + (f" + {other.name} (two mics: speaker labels)" if other else ""),
          flush=True)
    with tempfile.TemporaryDirectory() as work:
        transcript = source if source.suffix.lower() in TRANSCRIPT_EXTS else transcribe(source, work)
        if other:
            transcript = label_speakers(source, other, transcript, work)
        lines = load_transcript(transcript)
    cleaned = None
    if want_cleanup(args, model.choice, lines):
        cleaned, fallbacks = clean_lines(lines, model)
        cleanup.update(ran=True, lines=cleanup.get("lines", 0) + len(lines),
                       fallbacks=cleanup.get("fallbacks", 0) + fallbacks)
    print(f"[process] {len(lines)} lines", flush=True)
    return source, lines, cleaned


def find_recordings(folder):
    """Folder -> recordings found, grouped into proposed sittings (the same
    mtime-gap heuristic as `process`). This only looks and proposes -- it never
    asks and never guesses; the caller (an interactive prompt, or an agent
    reading this grouping) confirms it before anything is processed."""
    sources = sorted(
        (p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in RECORDING_EXTS),
        key=lambda p: p.stat().st_mtime,
    )
    if not sources:
        raise RunError(f"no recordings found in {folder}")
    return propose_groups(sources) if len(sources) > 1 else [sources]


def cmd_find(args):
    folder = Path(args.folder)
    if not folder.is_dir():
        raise RunError(f"no such folder: {folder}")
    return find_recordings(folder)


def cmd_transcribe(args):
    """One recording -> a segments file written beside it (or at --out)."""
    recording = Path(args.recording)
    if not recording.is_file():
        raise RunError(f"no such file: {recording}")
    if recording.suffix.lower() in TRANSCRIPT_EXTS:
        raise RunError(f"{recording} is already a transcript; nothing to transcribe")
    dest = Path(args.out) if args.out else recording.with_suffix(".segments.txt")
    with tempfile.TemporaryDirectory() as work:
        segments = transcribe(recording, work)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(segments, dest)
    st = recording.stat()
    os.utime(dest, (st.st_atime, st.st_mtime))  # the transcript dates (and groups) as its recording
    return dest


def cmd_render(args):
    """An action-items JSON file (render_action_items_html's schema) -> a
    self-contained HTML view written beside it (or at --out)."""
    try:
        data = json.loads(Path(args.items).read_text())
    except (OSError, json.JSONDecodeError) as e:
        raise RunError(f"couldn't read {args.items}: {e}")
    out = Path(args.out) if args.out else Path(args.items).with_suffix(".html")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_html(data))
    return out


def cmd_write(args):
    """write_to_brain's entry point: a dated block appended to one named,
    Brain-relative note. The invariants (never overwrite, all or nothing) are
    brain_writer's, not this function's -- it only builds the text and the
    relative path and hands both to write_to_brain()."""
    profile = load_or_setup_profile()
    if args.file:
        try:
            text = Path(args.file).read_text()
        except OSError as e:
            raise RunError(f"couldn't read {args.file}: {e}")
    else:
        text = args.text
    now = datetime.datetime.now()
    body = f"## {now.strftime('%Y-%m-%d %H:%M')}\n\n{text.strip()}\n"
    return write_to_brain(brain_root(profile), [(args.note, body)])


def local_version():
    return (HERE.parent / "VERSION").read_text().strip()


def latest_version(url):
    try:
        # ponytail: one 5 s fetch, no retry; offline just reports "couldn't check". Add backoff if doctor runs unattended.
        with urllib.request.urlopen(url, timeout=5) as r:  # noqa: S310 - fixed, operator-controlled URL
            return r.read().decode().strip(), None
    except (urllib.error.URLError, ValueError, OSError) as e:
        return None, str(e)


def doctor(args):
    """-> (checks, exit_code). Each check: {name, ok, detail}."""
    checks = []

    data = None
    try:
        data = load_profile_migrating()
        checks.append({"name": "profile", "ok": True, "detail": f"valid Profile at {profile_mod.profile_path()}"})
    except profile_mod.ProfileError as e:
        checks.append({"name": "profile", "ok": False, "detail": str(e)})

    try:
        if data is None:
            raise profile_mod.ProfileError("no valid Profile to check the Brain against")
        root = Path(data["brain"]["root"]).expanduser()
        root.mkdir(parents=True, exist_ok=True)
        writable = os.access(root, os.W_OK)
        checks.append({"name": "brain", "ok": writable,
                       "detail": f"{root} ({'writable' if writable else 'not writable'})"})
    except (profile_mod.ProfileError, OSError) as e:
        checks.append({"name": "brain", "ok": False, "detail": str(e)})

    ffmpeg = shutil.which("ffmpeg")
    checks.append({"name": "ffmpeg", "ok": bool(ffmpeg), "detail": ffmpeg or "not found on PATH"})

    url = os.environ.get("MEETING_LOOP_VERSION_URL", DEFAULT_VERSION_URL)
    local = local_version()
    remote, err = latest_version(url) if url else (None, None)
    if not url:
        checks.append({"name": "version", "ok": True, "detail": f"local {local}; no version check configured"})
    elif err:
        checks.append({"name": "version", "ok": True, "detail": f"local {local}; could not check for updates: {err}"})
    elif remote == local:
        checks.append({"name": "version", "ok": True, "detail": f"local {local}; up to date"})
    else:
        checks.append({"name": "version", "ok": True,
                       "detail": f"local {local}; newer version available: {remote}"})

    for c in checks:
        mark = "PASS" if c["ok"] else "FAIL"
        print(f"[doctor] {mark} {c['name']}: {c['detail']}")
    return checks


INSTALL_MARKER = ".meeting-loop-installed"
AGENT_MARK = "Installed by Meeting Loop. meeting-loop uninstall removes this file."  # install.sh appends it


def uninstall(args):
    """Remove what install.sh recorded in ~/.meeting-loop/installed.txt, then
    ~/.meeting-loop itself. Each recorded path is checked before it goes: a skill
    folder only with install.sh's marker in it, the command link only while it
    points here, a cache only if it is a Hugging Face model folder. The Brain and
    recordings live elsewhere and are never touched. -> list of what was removed."""
    root = Path.home() / ".meeting-loop"
    record = root / "installed.txt"
    if not record.is_file():
        raise RunError(f"Meeting Loop isn't installed here (no {record}); nothing to remove")
    plan, mcp = [], False
    for line in record.read_text().splitlines():
        kind, _, value = line.partition(" ")
        path = Path(value)
        if kind == "skill" and not path.is_symlink() and (path / INSTALL_MARKER).is_file():
            plan.append(path)
        elif kind == "agent" and path.is_file() and not path.is_symlink() and AGENT_MARK in path.read_text():
            plan.append(path)
        elif kind == "link" and path.is_symlink() and Path(os.readlink(path)) == root / "bin" / "meeting-loop":
            plan.append(path)
        elif kind == "cache" and path.name.startswith("models--") and path.is_dir():
            plan.append(path)
        elif kind == "mcp" and value == "claude":
            mcp = True
    plan.append(root)
    print("[uninstall] this removes:")
    for p in plan:
        print(f"  {p}")
    if mcp:
        print("  the meeting-loop MCP server in Claude Code")
    if not args.yes:
        if not sys.stdin.isatty():
            raise RunError("nothing removed; run `meeting-loop uninstall --yes` to confirm")
        if input("Remove these? [y/N] ").strip().lower() not in ("y", "yes"):
            raise RunError("nothing removed")
    if mcp and shutil.which("claude"):
        subprocess.run(["claude", "mcp", "remove", "--scope", "user", "meeting-loop"],
                       stdin=subprocess.DEVNULL, capture_output=True)
    for p in plan:
        if p.is_symlink() or p.is_file():
            p.unlink()
        else:
            shutil.rmtree(p, ignore_errors=True)
    print("[uninstall] done. Your Brain and recordings were left where they are.")
    return [str(p) for p in plan]


CONSENT_REMINDER = ("Tell everyone in the room they're being recorded before you start. "
                    "Some places require every person's consent, not only yours.")


def record(args):
    """Start the Mac mic in the background (recorder/record.sh), or stop it with
    --stop. -> result dict for the MEETING_LOOP_RESULT line. The state file is
    how --stop finds the recorder an earlier `record` started."""
    state = Path.home() / ".meeting-loop" / "recording.json"
    if args.stop:
        if not state.exists():
            raise RunError("nothing is recording")
        rec = json.loads(state.read_text())
        _stop_group(rec["pid"])
        state.unlink()
        wav = Path(rec["file"])
        if not wav.is_file() or wav.stat().st_size == 0:
            raise RunError(f"no audio was captured; recorder log: {rec['log']}")
        print(f"[record] saved {wav}")
        print(f"[record] next: meeting-loop process {shlex.quote(str(wav))}")
        return {"ok": True, "files": [str(wav)]}

    if state.exists() and _alive(json.loads(state.read_text())["pid"]):
        raise RunError("already recording; stop it first with: meeting-loop record --stop")
    print(f"[record] {CONSENT_REMINDER}", flush=True)
    state.parent.mkdir(parents=True, exist_ok=True)
    log = state.with_name("recording.log")
    env = dict(os.environ)
    env.setdefault("REC_DIR", str(Path.home() / "MeetingLoop" / "Recordings"))
    with open(log, "w") as out:
        proc = subprocess.Popen(["bash", str(HERE.parent / "recorder" / "record.sh"), "meeting"],
                                stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT,
                                env=env, start_new_session=True)
    # "Recording" is claimed only once the mic is open and the file exists: a mic that
    # never opens (no permission, a vanished device) must not look like a recording.
    deadline = time.time() + 10
    wav = None
    while time.time() < deadline:
        m = re.search(r"^File\s*:\s*(.+)$", log.read_text(), re.M)
        wav = m[1].strip() if m else None
        if wav and Path(wav).is_file():  # ffmpeg creates it once the mic is open
            break
        if proc.poll() is not None:
            raise RunError("the recorder stopped before it started: " + log.read_text().strip()[-300:])
        time.sleep(0.1)
    else:
        _stop_group(proc.pid)
        raise RunError("the mic didn't start within 10 seconds; check that your terminal app has "
                       "microphone access (System Settings > Privacy & Security > Microphone)")
    state.write_text(json.dumps({"pid": proc.pid, "file": wav, "log": str(log)}))
    print(f"[record] recording to {wav}")
    print("[record] stop with: meeting-loop record --stop")
    return {"ok": True, "recording": wav, "files": []}


def _stop_group(pid):
    """SIGINT first (ffmpeg finalizes the WAV), then harder if the recorder ignores it."""
    # ponytail: fixed escalation (10 s for ffmpeg to finalize the WAV). A very long take on a slow disk could
    # need more; make `wait` scale with file size if a stop ever truncates.
    for sig, wait in ((signal.SIGINT, 10), (signal.SIGTERM, 3), (signal.SIGKILL, 2)):
        try:
            os.killpg(pid, sig)
        except ProcessLookupError:
            return
        deadline = time.time() + wait
        while time.time() < deadline:
            if not _alive(pid):
                return
            time.sleep(0.1)


def _alive(pid):
    try:
        if os.waitpid(pid, os.WNOHANG)[0] == pid:  # our own child that has exited
            return False
    except ChildProcessError:
        pass  # not our child (started by an earlier `record`); ask the OS instead
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def main(argv=None):
    ap = argparse.ArgumentParser(prog="meeting-loop")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("process", help="turn one or more recordings into notes in your Brain")
    p.add_argument("recordings", nargs="+", metavar="recording")
    p.add_argument("--type", help="meeting type id (see meeting-types.json); asked when omitted")
    sit_group = p.add_mutually_exclusive_group()
    sit_group.add_argument("--yes", action="store_true",
                           help="accept the proposed sitting grouping without asking (for agents that already showed it)")
    sit_group.add_argument("--sitting", action="store_true",
                           help="treat every recording given as one sitting")
    entity_group = p.add_mutually_exclusive_group()
    entity_group.add_argument("--entity", help="entity note to append a dated entry to; asked when omitted")
    entity_group.add_argument("--no-entity", action="store_true", help="skip the entity note; don't ask")
    clean_group = p.add_mutually_exclusive_group()
    clean_group.add_argument("--clean", dest="clean", action="store_true", default=None,
                             help="clean up transcript wording with the on-device model (default on 16 GB+ Macs)")
    clean_group.add_argument("--no-clean", dest="clean", action="store_false",
                             help="skip cleanup; the raw transcript is always kept either way")
    p.add_argument("--llm", choices=["local", "none", "agent"], default="local",
                   help="local: on-device model (default); none: no model, keyword action items; "
                        "agent: candidate action items supplied via --agent-items")
    p.add_argument("--agent-items", metavar="PATH",
                   help="JSON file of candidate action items ([{task, quote, ...}]) for --llm agent; "
                        "the quote check still gates every one of them")

    s = sub.add_parser("setup", help="answer three questions and write your Profile")
    s.add_argument("--brain", default=None, help="where your Brain (notes) should live")
    s.add_argument("--mics", choices=["one", "two"], default=None)
    s.add_argument("--types", default=None, help="comma-separated meeting type ids")
    s.add_argument("--yes", action="store_true", help="accept recommended defaults for anything not passed")

    sub.add_parser("doctor", help="check your setup and, only now, whether a newer version exists")

    f = sub.add_parser("find", help="find recordings in a folder and propose sitting groups")
    f.add_argument("folder")

    t = sub.add_parser("transcribe", help="transcribe one recording to a segments file")
    t.add_argument("recording")
    t.add_argument("--out", default=None, help="where to write the transcript; default beside the recording")

    r = sub.add_parser("render", help="render an action-items JSON file to a self-contained HTML view")
    r.add_argument("items", metavar="items.json")
    r.add_argument("--out", default=None, help="where to write the HTML; default beside the items file")

    w = sub.add_parser("write", help="append a dated block to a note in your Brain")
    w.add_argument("note", help="path relative to your Brain root, e.g. Entities/acme.md")
    wg = w.add_mutually_exclusive_group(required=True)
    wg.add_argument("--text", help="the text to append")
    wg.add_argument("--file", help="read the text to append from this file")

    sub.add_parser("version", help="print the installed version")

    rec = sub.add_parser("record", help="start recording the Mac mic in the background; --stop ends it")
    rec.add_argument("--stop", action="store_true", help="stop the recording and print its file")

    u = sub.add_parser("uninstall", help="remove what install.sh installed; your Brain and recordings stay")
    u.add_argument("--yes", action="store_true", help="don't ask for confirmation")

    args = ap.parse_args(argv)

    if args.cmd == "uninstall":
        try:
            removed = uninstall(args)
        except RunError as e:
            print(f"meeting-loop: {e}", file=sys.stderr)
            print(f"{RESULT} " + json.dumps({"ok": False, "error": str(e), "files": []}))
            return 1
        print(f"{RESULT} " + json.dumps({"ok": True, "removed": removed, "files": []}))
        return 0

    if args.cmd == "record":
        try:
            result = record(args)
        except RunError as e:
            print(f"meeting-loop: {e}", file=sys.stderr)
            print(f"{RESULT} " + json.dumps({"ok": False, "error": str(e), "files": []}))
            return 1
        print(f"{RESULT} " + json.dumps(result))
        return 0

    if args.cmd == "setup":
        types = [t.strip() for t in args.types.split(",") if t.strip()] if args.types else None
        interactive = False if args.yes else None
        try:
            run_setup(brain=args.brain, mics=args.mics, types=types, interactive=interactive)
        except RunError as e:
            print(f"meeting-loop: {e}", file=sys.stderr)
            return 1
        return 0

    if args.cmd == "doctor":
        checks = doctor(args)
        ok = all(c["ok"] for c in checks)
        print(f"{DOCTOR_RESULT} " + json.dumps({"ok": ok, "checks": checks}))
        return 0 if ok else 1

    if args.cmd == "find":
        try:
            groups = cmd_find(args)
        except RunError as e:
            print(f"meeting-loop: {e}", file=sys.stderr)
            print(f"{RESULT} " + json.dumps({"ok": False, "error": str(e)}))
            return 1
        for i, g in enumerate(groups, 1):
            print(f"[find] group {i}: " + ", ".join(p.name for p in g))
        print(f"{RESULT} " + json.dumps({"ok": True, "groups": [[str(p) for p in g] for g in groups]}))
        return 0

    if args.cmd == "transcribe":
        try:
            dest = cmd_transcribe(args)
        except RunError as e:
            print(f"meeting-loop: {e}", file=sys.stderr)
            print(f"{RESULT} " + json.dumps({"ok": False, "error": str(e), "files": []}))
            return 1
        print(f"[transcribe] wrote {dest}")
        print(f"{RESULT} " + json.dumps({"ok": True, "files": [str(dest)]}))
        return 0

    if args.cmd == "render":
        try:
            out = cmd_render(args)
        except RunError as e:
            print(f"meeting-loop: {e}", file=sys.stderr)
            print(f"{RESULT} " + json.dumps({"ok": False, "error": str(e), "files": []}))
            return 1
        print(f"[render] wrote {out}")
        print(f"{RESULT} " + json.dumps({"ok": True, "files": [str(out)]}))
        return 0

    if args.cmd == "write":
        try:
            files = cmd_write(args)
        except (RunError, BrainWriteError) as e:
            print(f"meeting-loop: {e}", file=sys.stderr)
            print(f"{RESULT} " + json.dumps({"ok": False, "error": str(e), "files": []}))
            return 1
        for f in files:
            print(f"[brain] {f}")
        print(f"{RESULT} " + json.dumps({"ok": True, "files": [str(f) for f in files]}))
        return 0

    if args.cmd == "version":
        v = local_version()
        print(v)
        print(f"{RESULT} " + json.dumps({"ok": True, "version": v}))
        return 0

    try:
        files, kept, dropped, note, cleanup = process(args)
    except (RunError, BrainWriteError) as e:
        print(f"meeting-loop: {e}", file=sys.stderr)
        print(f"{RESULT} " + json.dumps({"ok": False, "error": str(e), "files": []}))
        return 1
    for f in files:
        print(f"[brain] {f}")
    result = {"ok": True, "files": [str(f) for f in files], "action_items": {"kept": kept, "dropped": dropped},
              "cleanup": cleanup}
    if note:
        result["note"] = note
    print(f"{RESULT} " + json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
