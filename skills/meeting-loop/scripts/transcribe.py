#!/usr/bin/env python3
"""
transcribe.py — one audio file -> JSON + clean text + timestamped segments.

Local, Metal-accelerated transcription via mlx-whisper. Reads WAV/FLAC/OGG
directly with soundfile (no ffmpeg needed); for M4A/AAC/MP4/MOV or anything
soundfile can't decode, it transparently shells out to `ffmpeg` to convert to
16 kHz mono WAV first (fully local — no cloud). Resamples to 16 kHz mono, runs
Whisper, and strips the silence-hallucination loops Whisper sometimes emits on
quiet passages (runs of identical-timestamp / duplicate segments).

Usage:
    python3 transcribe.py INPUT OUT_PREFIX [--model REPO] [--language LANG]
                          [--prompt "names + jargon"] [--force]

    --language auto  → let Whisper detect the language (default: en)
    --prompt TEXT    → seed Whisper with known proper nouns (speaker names,
                       client name, the jargon and product names you use) so
                       it stops mangling them. Maps to Whisper's initial_prompt.
    --force          → re-transcribe even if outputs already exist (default:
                       skip a file whose .json/.txt/.segments.txt are all present,
                       so a multi-file run that died partway resumes cheaply).

Writes:
    OUT_PREFIX.json           full Whisper result
    OUT_PREFIX.txt            cleaned plain transcript
    OUT_PREFIX.segments.txt   [hh:mm:ss -> hh:mm:ss] text, one per line

Intended to run inside the persistent venv at
~/.cache/mlx-whisper-transcribe/venv (see setup_env.sh).
"""
import argparse
import json
import os
import sys
import time

DEFAULT_MODEL = os.environ.get("CML_WHISPER_MODEL", "mlx-community/whisper-large-v3-turbo")


def fmt_ts(t):
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


# Formats libsndfile can't decode — go straight to ffmpeg for these.
_FFMPEG_EXTS = {".m4a", ".aac", ".mp4", ".mov", ".m4b", ".caf", ".wma", ".amr"}


def _ffmpeg_to_wav(path):
    """Decode any container ffmpeg understands to a temp 16 kHz mono WAV.

    Local only — ffmpeg touches no network. Returns the temp WAV path; caller
    is responsible for reading it (we leave cleanup to the OS temp dir).
    """
    import shutil
    import subprocess
    import tempfile
    if not shutil.which("ffmpeg"):
        sys.exit(
            f"[error] '{path}' needs ffmpeg to decode, but ffmpeg isn't on PATH.\n"
            "Install it once: brew install ffmpeg  (local, no cloud)."
        )
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    print(f"[convert] {os.path.basename(path)} -> 16 kHz mono WAV via ffmpeg", flush=True)
    proc = subprocess.run(
        ["ffmpeg", "-y", "-i", path, "-ac", "1", "-ar", "16000",
         "-c:a", "pcm_s16le", tmp.name],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        sys.exit(f"[error] ffmpeg failed on '{path}':\n{proc.stderr.strip()[-800:]}")
    return tmp.name


def load_audio(path):
    import soundfile as sf
    import numpy as np
    ext = os.path.splitext(path)[1].lower()
    read_path = path
    if ext in _FFMPEG_EXTS:
        read_path = _ffmpeg_to_wav(path)
    try:
        audio, sr = sf.read(read_path, dtype="float32", always_2d=False)
    except Exception as e:
        # Last resort: let ffmpeg try anything soundfile choked on.
        if read_path == path:
            try:
                read_path = _ffmpeg_to_wav(path)
                audio, sr = sf.read(read_path, dtype="float32", always_2d=False)
            except SystemExit:
                raise
            except Exception as e2:
                sys.exit(f"[error] could not read '{path}' (soundfile: {e}; ffmpeg fallback: {e2})")
        else:
            sys.exit(f"[error] could not read converted '{path}': {e}")
    if audio.ndim > 1:  # mixdown to mono
        audio = audio.mean(axis=1)
    return audio.astype(np.float32), sr


def resample_to_16k(audio, sr):
    if sr == 16000:
        return audio, sr
    import numpy as np
    from math import gcd
    from scipy.signal import resample_poly
    g = gcd(int(sr), 16000)
    up, down = 16000 // g, int(sr) // g
    return resample_poly(audio, up, down).astype(np.float32), 16000


def strip_hallucinations(segments):
    """Remove Whisper's silence-loop artifacts.

    Drops: zero/near-zero-duration empty segments, and consecutive segments
    whose text repeats the immediately preceding kept segment.
    """
    cleaned = []
    prev_text = None
    for seg in segments:
        text = seg.get("text", "").strip()
        dur = float(seg.get("end", 0)) - float(seg.get("start", 0))
        if not text:
            continue
        if dur <= 0.05 and text == prev_text:
            continue
        if text == prev_text:
            # exact repeat of previous line -> hallucination loop
            continue
        cleaned.append(seg)
        prev_text = text
    return cleaned


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("out_prefix")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--language", default="en")
    ap.add_argument("--prompt", default=None,
                    help="initial_prompt — known names/jargon to prime Whisper")
    ap.add_argument("--force", action="store_true",
                    help="re-transcribe even if outputs already exist")
    args = ap.parse_args()

    # Resumability: skip a file already fully transcribed (all 3 outputs present
    # and non-empty), unless --force. Lets a dead multi-file run resume cheaply.
    outs = [args.out_prefix + ext for ext in (".json", ".txt", ".segments.txt")]
    if not args.force and all(os.path.exists(p) and os.path.getsize(p) > 0 for p in outs):
        print(f"[skip] {args.out_prefix}.* already present — pass --force to redo", flush=True)
        return

    import mlx_whisper
    import numpy as np

    t0 = time.time()
    print(f"[load] {args.input}", flush=True)
    audio, sr = load_audio(args.input)
    print(f"[load] sr={sr} samples={len(audio)} dur={len(audio)/sr/60:.1f}min ({time.time()-t0:.1f}s)", flush=True)

    audio, sr = resample_to_16k(audio, sr)
    peak = float(np.max(np.abs(audio))) or 1.0
    if peak > 1.0:
        audio = audio / peak

    # --language auto -> None lets Whisper detect it per-file.
    lang = None if args.language.lower() == "auto" else args.language
    prompt_note = f" prompt={len(args.prompt)}ch" if args.prompt else ""
    print(f"[transcribe] model={args.model} language={lang or 'auto'}{prompt_note} ({time.time()-t0:.1f}s elapsed)", flush=True)
    result = mlx_whisper.transcribe(
        audio,
        path_or_hf_repo=args.model,
        language=lang,
        initial_prompt=args.prompt,
        word_timestamps=False,
        condition_on_previous_text=True,
        verbose=False,
    )

    raw_segs = result.get("segments", [])
    segs = strip_hallucinations(raw_segs)
    dropped = len(raw_segs) - len(segs)
    print(f"[transcribe] done ({time.time()-t0:.1f}s) — {len(segs)} segments ({dropped} hallucination lines stripped)", flush=True)

    clean_text = " ".join(s["text"].strip() for s in segs).strip()

    with open(args.out_prefix + ".json", "w") as f:
        json.dump(result, f, indent=2)
    with open(args.out_prefix + ".txt", "w") as f:
        f.write(clean_text + "\n")
    with open(args.out_prefix + ".segments.txt", "w") as f:
        for s in segs:
            f.write(f"[{fmt_ts(s['start'])} -> {fmt_ts(s['end'])}] {s['text'].strip()}\n")

    print(f"[write] {args.out_prefix}.{{json,txt,segments.txt}} ({time.time()-t0:.1f}s total)", flush=True)


if __name__ == "__main__":
    main()
