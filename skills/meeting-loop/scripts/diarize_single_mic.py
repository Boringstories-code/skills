#!/usr/bin/env python3
"""
diarize_single_mic.py — speaker separation from ONE recorder of a multi-speaker
meeting, using pyannote.audio 3.1. The fallback for when there weren't two lavs.

Pipeline:
  1. Run pyannote/speaker-diarization-3.1 on the audio -> speaker turns
     (start, end, SPEAKER_xx). Runs on CPU (pyannote's MPS path on Apple
     Silicon is incomplete / often slower — CPU is the reliable choice).
  2. Read the transcript's .segments.txt (from transcribe.py).
  3. Tag each transcript segment with the speaker whose turns overlap it most.
  4. Write attributed segments in the SAME format as diarize_two_mic.py, so
     everything downstream (transcript-cleaner etc.) is unchanged:
        [hh:mm:ss.mmm -> hh:mm:ss.mmm] Speaker: text

Fully local once the model is cached. The pyannote models are HF-gated: the
FIRST download needs an HF token and you must accept the terms for BOTH
'pyannote/speaker-diarization-3.1' and 'pyannote/segmentation-3.0' on
huggingface.co. After that it runs offline (set HF_HUB_OFFLINE=1 to force it).

Usage:
    python3 diarize_single_mic.py \
        --audio meeting.wav \
        --segments meeting.segments.txt \
        --out meeting.attributed.segments.txt \
        [--num-speakers 3] [--min-speakers 2] [--max-speakers 5] \
        [--names SPEAKER_00=Dana,SPEAKER_01=Rae] \
        [--timeline meeting.timeline.json]

Token is read from --hf-token or env HF_TOKEN / HUGGINGFACE_TOKEN /
HUGGING_FACE_HUB_TOKEN. Not needed once the model is cached.

Install (kept OUT of the base venv — it's heavy): scripts/setup_diarization.sh
"""
import argparse
import json
import os
import re
import sys


def die(msg):
    sys.exit(f"[error] {msg}")


def load_pipeline(token):
    try:
        from pyannote.audio import Pipeline
    except Exception as e:
        die("pyannote.audio isn't installed in this venv. Run "
            "scripts/setup_diarization.sh once.\n        (import error: %s)" % e)
    try:
        import torch
    except Exception as e:
        die(f"torch isn't available: {e}")

    kwargs = {}
    if token:
        kwargs["use_auth_token"] = token
    try:
        pipe = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1", **kwargs)
    except Exception as e:
        die(
            "could not load 'pyannote/speaker-diarization-3.1'.\n"
            "        First run needs an HF token AND you must accept the model terms for\n"
            "        both pyannote/speaker-diarization-3.1 and pyannote/segmentation-3.0\n"
            "        at huggingface.co. Pass --hf-token or set HF_TOKEN.\n"
            f"        (loader error: {e})"
        )
    if pipe is None:
        die("pyannote returned no pipeline — the model terms are probably not accepted "
            "for your token yet (accept them on huggingface.co).")
    pipe.to(torch.device("cpu"))  # MPS is unreliable for this pipeline
    return pipe


def parse_ts(s):
    h, m, sec = s.split(":")
    return int(h) * 3600 + int(m) * 60 + float(sec)


def parse_names(spec):
    if not spec:
        return {}
    out = {}
    for pair in spec.split(","):
        pair = pair.strip()
        if "=" in pair:
            k, v = pair.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", required=True)
    ap.add_argument("--segments", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--num-speakers", type=int, default=None)
    ap.add_argument("--min-speakers", type=int, default=None)
    ap.add_argument("--max-speakers", type=int, default=None)
    ap.add_argument("--names", default=None,
                    help="rename labels, e.g. SPEAKER_00=Dana,SPEAKER_01=Rae")
    ap.add_argument("--timeline", default=None)
    ap.add_argument("--hf-token", default=None)
    args = ap.parse_args()

    if not os.path.exists(args.audio):
        die(f"audio not found: {args.audio}")
    if not os.path.exists(args.segments):
        die(f"segments file not found: {args.segments}")

    token = (args.hf_token or os.environ.get("HF_TOKEN")
             or os.environ.get("HUGGINGFACE_TOKEN")
             or os.environ.get("HUGGING_FACE_HUB_TOKEN"))

    print("[diarize] loading pyannote speaker-diarization-3.1 (CPU)…", flush=True)
    pipe = load_pipeline(token)

    diar_kwargs = {}
    if args.num_speakers is not None:
        diar_kwargs["num_speakers"] = args.num_speakers
    else:
        if args.min_speakers is not None:
            diar_kwargs["min_speakers"] = args.min_speakers
        if args.max_speakers is not None:
            diar_kwargs["max_speakers"] = args.max_speakers

    print(f"[diarize] running on {args.audio} {diar_kwargs or '(auto speaker count)'}…", flush=True)
    diarization = pipe(args.audio, **diar_kwargs)

    names = parse_names(args.names)

    # Collect speaker turns; build a merged timeline for optional export.
    turns = []  # (start, end, label)
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        turns.append((float(turn.start), float(turn.end), names.get(speaker, speaker)))
    turns.sort(key=lambda x: x[0])
    labels = sorted({t[2] for t in turns})
    print(f"[diarize] {len(turns)} turns across {len(labels)} speakers: {', '.join(labels)}", flush=True)

    if args.timeline:
        json.dump([{"start": round(s, 2), "end": round(e, 2), "speaker": sp}
                   for s, e, sp in turns], open(args.timeline, "w"), indent=2)

    def speaker_for(t0, t1):
        """Speaker whose turns overlap [t0,t1] most; nearest turn if no overlap."""
        best, best_ov = None, 0.0
        for s, e, sp in turns:
            ov = min(t1, e) - max(t0, s)
            if ov > best_ov:
                best_ov, best = ov, sp
        if best is not None:
            return best
        # no overlap (short seg in a gap) — snap to the nearest turn by midpoint
        mid = (t0 + t1) / 2
        if not turns:
            return labels[0] if labels else "SPEAKER_00"
        return min(turns, key=lambda t: min(abs(mid - t[0]), abs(mid - t[1])))[2]

    line_re = re.compile(r"\[(\d\d:\d\d:[\d.]+) -> (\d\d:\d\d:[\d.]+)\]\s*(.*)")
    out_lines, n, unknown = [], 0, 0
    for raw in open(args.segments):
        m = line_re.match(raw.strip())
        if not m:
            continue
        a, b, text = m.group(1), m.group(2), m.group(3)
        sp = speaker_for(parse_ts(a), parse_ts(b))
        out_lines.append(f"[{a} -> {b}] {sp}: {text}")
        n += 1
    open(args.out, "w").write("\n".join(out_lines) + "\n")
    print(f"[diarize] wrote {n} attributed segments -> {args.out}", flush=True)
    if not names:
        print("[diarize] labels are SPEAKER_xx — map them to real names with --names "
              "(or let the cleaner agent do it from the intro).", flush=True)


if __name__ == "__main__":
    main()
