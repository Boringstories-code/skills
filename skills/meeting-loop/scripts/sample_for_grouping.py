#!/usr/bin/env python3
"""sample_for_grouping.py — cheap start/mid/end WAV for Step 1 grouping.

Does NOT run Whisper and does NOT decide groups. Writes a 16 kHz mono WAV.
The agent transcribes that with transcribe.py, proposes sessions, and waits.

Usage:
    python3 sample_for_grouping.py INPUT -o OUT_PREFIX [--force]
    python3 sample_for_grouping.py --selftest

Writes:
    OUT_PREFIX.sample.wav

A file shorter than WHOLE_FILE_BELOW_S is converted whole (start/mid/end would
overlap). Longer files: ~180s start + ~90s at 1/3 + ~75s end, 1s silence
between — the 2026-09-19 Voice Memo recipe.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile

WHOLE_FILE_BELOW_S = 360.0
START_S = 180.0
MID_S = 90.0
END_S = 75.0


def _need_ffmpeg():
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        sys.exit(
            "[error] ffmpeg/ffprobe not on PATH.\n"
            "Install once: brew install ffmpeg  (local, no cloud)."
        )


def probe_duration(path: str) -> float:
    r = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=nw=1:nk=1",
            path,
        ],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        sys.exit(f"[error] ffprobe failed on '{path}':\n{(r.stderr or '')[-400:]}")
    try:
        dur = float(r.stdout.strip())
    except ValueError:
        sys.exit(f"[error] ffprobe gave no duration for '{path}'")
    if dur <= 0:
        sys.exit(f"[error] duration is {dur} for '{path}'")
    return dur


def _run_ffmpeg(cmd: list[str], what: str) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"[error] ffmpeg {what}:\n{(r.stderr or '')[-800:]}")


def extract(path: str, out_wav: str, *, force: bool = False) -> str:
    _need_ffmpeg()
    if not os.path.isfile(path):
        sys.exit(f"[error] no file: {path}")
    os.makedirs(os.path.dirname(os.path.abspath(out_wav)) or ".", exist_ok=True)
    if os.path.isfile(out_wav) and os.path.getsize(out_wav) > 10_000 and not force:
        print(f"[skip] {out_wav}", flush=True)
        return "skip"
    dur = probe_duration(path)
    if dur < WHOLE_FILE_BELOW_S:
        _run_ffmpeg(
            [
                "ffmpeg",
                "-y",
                "-i",
                path,
                "-ac",
                "1",
                "-ar",
                "16000",
                "-c:a",
                "pcm_s16le",
                out_wav,
            ],
            "whole-file convert",
        )
        print(f"[sample] whole {dur:.1f}s -> {out_wav}", flush=True)
        return "whole"
    start_d = min(START_S, dur)
    mid_t = max(0.0, dur / 3.0)
    mid_d = min(MID_S, max(0.0, dur - mid_t))
    end_d = min(END_S, dur)
    end_t = max(0.0, dur - end_d)
    fc = (
        f"[0:a]atrim=start=0:duration={start_d:.2f},asetpts=PTS-STARTPTS[a0];"
        f"aevalsrc=0:d=1.0[s1];"
        f"[0:a]atrim=start={mid_t:.2f}:duration={mid_d:.2f},asetpts=PTS-STARTPTS[a1];"
        f"aevalsrc=0:d=1.0[s2];"
        f"[0:a]atrim=start={end_t:.2f}:duration={end_d:.2f},asetpts=PTS-STARTPTS[a2];"
        f"[a0][s1][a1][s2][a2]concat=n=5:v=0:a=1[out]"
    )
    _run_ffmpeg(
        [
            "ffmpeg",
            "-y",
            "-i",
            path,
            "-filter_complex",
            fc,
            "-map",
            "[out]",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            out_wav,
        ],
        "windows concat",
    )
    print(f"[sample] windows {dur:.1f}s -> {out_wav}", flush=True)
    return "windows"


def _selftest() -> int:
    _need_ffmpeg()
    work = tempfile.mkdtemp(prefix="ml-sample-")
    short_in = os.path.join(work, "short.wav")
    long_in = os.path.join(work, "long.wav")
    short_out = os.path.join(work, "short.sample.wav")
    long_out = os.path.join(work, "long.sample.wav")
    _run_ffmpeg(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=8",
            "-ac",
            "1",
            "-ar",
            "16000",
            short_in,
        ],
        "selftest short src",
    )
    _run_ffmpeg(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=16000:cl=mono:d=400",
            "-ac",
            "1",
            "-ar",
            "16000",
            long_in,
        ],
        "selftest long src",
    )
    if extract(short_in, short_out, force=True) != "whole":
        print("[selftest] FAIL short path was not whole-file", file=sys.stderr)
        return 1
    sd = probe_duration(short_out)
    if not (7.0 <= sd <= 9.0):
        print(f"[selftest] FAIL short duration {sd}", file=sys.stderr)
        return 1
    if extract(long_in, long_out, force=True) != "windows":
        print("[selftest] FAIL long path was not windows", file=sys.stderr)
        return 1
    ld = probe_duration(long_out)
    # 180 + 1 + 90 + 1 + 75 = 347
    if not (340.0 <= ld <= 355.0):
        print(f"[selftest] FAIL long duration {ld} (want ~347)", file=sys.stderr)
        return 1
    print("[selftest] sample_for_grouping OK")
    shutil.rmtree(work, ignore_errors=True)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input", nargs="?", help="audio file")
    ap.add_argument("-o", "--out-prefix", help="writes OUT_PREFIX.sample.wav")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return _selftest()
    if not a.input or not a.out_prefix:
        ap.error("INPUT and -o OUT_PREFIX are required (or pass --selftest)")
    out_wav = a.out_prefix + ".sample.wav"
    extract(a.input, out_wav, force=a.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
