#!/usr/bin/env python3
"""
chords.py — audio file -> timestamped chord chart (local, no cloud).

Spotify Basic Pitch transcribes notes. A chroma+template matcher turns those
notes into chord symbols.

Usage:
    python3 chords.py INPUT OUT_PREFIX [--force]
    python3 chords.py --selftest

Writes:
    OUT_PREFIX.chords.json
    OUT_PREFIX.chords.md
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

PC = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
QUALITIES = {
    "": (0, 4, 7),
    "m": (0, 3, 7),
    "7": (0, 4, 7, 10),
    "maj7": (0, 4, 7, 11),
    "m7": (0, 3, 7, 10),
    "sus4": (0, 5, 7),
    "sus2": (0, 2, 7),
    "dim": (0, 3, 6),
    "aug": (0, 4, 8),
    "5": (0, 7),
}
# ponytail: no Viterbi; add if real tapes flicker between relatives
WIN = 1.0
HOP = 0.5
MIN_COS = 0.55
_FFMPEG_EXTS = {".m4a", ".aac", ".mp4", ".mov", ".m4b", ".caf", ".wma", ".amr"}


def fmt_ts(t):
    t = max(0.0, float(t))
    m = int(t // 60)
    s = t % 60
    return f"{m}:{s:05.2f}"


def _templates():
    import numpy as np
    out = []
    for root in range(12):
        for qual, ivs in QUALITIES.items():
            v = np.zeros(12, dtype=np.float64)
            for i in ivs:
                v[(root + i) % 12] = 1.0
            n = np.linalg.norm(v)
            out.append((f"{PC[root]}{qual}", root, v / n))
    return out


def notes_to_chords(notes, win=WIN, hop=HOP, min_cos=MIN_COS):
    import numpy as np
    if not notes:
        return []
    tpls = _templates()
    t_end = max(n["end"] for n in notes)
    raw = []
    t = 0.0
    while t < t_end - 0.05:
        w0, w1 = t, t + win
        chroma = np.zeros(12, dtype=np.float64)
        for n in notes:
            a, b = n["start"], n["end"]
            overlap = min(w1, b) - max(w0, a)
            if overlap <= 0:
                continue
            chroma[int(n["midi"]) % 12] += overlap * max(float(n["amp"]), 0.05)
        norm = np.linalg.norm(chroma)
        if norm < 1e-8:
            raw.append({"start": w0, "end": min(w1, t_end), "chord": "N", "conf": 0.0})
            t += hop
            continue
        chroma = chroma / norm
        best, best_s, best_root = "N", 0.0, None
        for label, root, vec in tpls:
            s = float(chroma @ vec)
            if s > best_s:
                best, best_s, best_root = label, s, root
        if best_root is not None and chroma[best_root] < 0.12:
            best, best_s = "N", 0.0
        if best_s < min_cos:
            best = "N"
        raw.append({"start": w0, "end": min(w1, t_end), "chord": best, "conf": round(best_s, 3)})
        t += hop
    return _merge(raw)


def _merge(raw, gap=0.26):
    if not raw:
        return []
    out = [dict(raw[0])]
    for seg in raw[1:]:
        prev = out[-1]
        if seg["chord"] == prev["chord"] and seg["start"] <= prev["end"] + gap:
            prev["end"] = seg["end"]
            prev["conf"] = round(max(prev["conf"], seg["conf"]), 3)
        else:
            out.append(dict(seg))
    return [s for s in out if s["end"] - s["start"] >= 0.4 or s["chord"] != "N"]


def guess_key(notes):
    import numpy as np
    if not notes:
        return None
    chroma = np.zeros(12, dtype=np.float64)
    for n in notes:
        chroma[int(n["midi"]) % 12] += (n["end"] - n["start"]) * max(float(n["amp"]), 0.05)
    major = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
    minor = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
    best, best_s = None, -1.0
    for i in range(12):
        rot = np.roll(chroma, -i)
        for mode, prof in (("", major), ("m", minor)):
            s = float(rot @ prof)
            if s > best_s:
                best, best_s = f"{PC[i]}{mode}", s
    return best


def _ffmpeg_wav(path):
    import shutil
    import subprocess
    import tempfile
    if not shutil.which("ffmpeg"):
        sys.exit(
            f"[error] '{path}' needs ffmpeg, and ffmpeg isn't on PATH.\n"
            "Install it once: brew install ffmpeg"
        )
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    proc = subprocess.run(
        ["ffmpeg", "-y", "-i", path, "-ac", "1", "-c:a", "pcm_s16le", tmp.name],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        sys.exit(f"[error] ffmpeg failed on '{path}':\n{proc.stderr.strip()[-800:]}")
    return tmp.name


def _note_events_to_notes(note_events):
    notes = []
    for ev in note_events:
        start, end, pitch, amp = ev[0], ev[1], ev[2], ev[3]
        notes.append({
            "start": float(start),
            "end": float(end),
            "midi": int(pitch),
            "amp": float(amp),
        })
    return notes


def run_basic_pitch(path):
    try:
        from basic_pitch.inference import predict
    except ImportError:
        sys.exit(
            "[error] basic-pitch is not installed in this venv.\n"
            "Run once: bash Skills/song-loop/scripts/setup_chords.sh"
        )
    ext = os.path.splitext(path)[1].lower()
    audio_path = _ffmpeg_wav(path) if ext in _FFMPEG_EXTS else path
    print(f"[basic-pitch] {os.path.basename(path)}", flush=True)
    _model_output, _midi, note_events = predict(audio_path)
    return _note_events_to_notes(note_events)


def render_md(segments, key, n_notes):
    lines = [
        "# Chords",
        "",
        f"Key guess: {key or '—'}",
        f"Engine: basic-pitch notes + templates ({n_notes} notes)",
        "",
        "| start | end | chord | conf |",
        "| --- | --- | --- | --- |",
    ]
    if not segments:
        lines.append("| — | — | N | 0 |")
    for s in segments:
        lines.append(f"| {fmt_ts(s['start'])} | {fmt_ts(s['end'])} | {s['chord']} | {s['conf']:.2f} |")
    lines.append("")
    compact = " | ".join(
        f"{fmt_ts(s['start'])} {s['chord']}" for s in segments if s["chord"] != "N"
    )
    if compact:
        lines.append(compact)
        lines.append("")
    return "\n".join(lines)


def selftest():
    c_notes = [
        {"start": 0.0, "end": 2.0, "midi": 60, "amp": 1.0},
        {"start": 0.0, "end": 2.0, "midi": 64, "amp": 1.0},
        {"start": 0.0, "end": 2.0, "midi": 67, "amp": 1.0},
    ]
    segs = notes_to_chords(c_notes)
    labels = [s["chord"] for s in segs if s["chord"] != "N"]
    assert labels and labels[0] == "C", labels
    assert guess_key(c_notes) == "C", guess_key(c_notes)

    am = [
        {"start": 0.0, "end": 2.0, "midi": 57, "amp": 1.0},
        {"start": 0.0, "end": 2.0, "midi": 60, "amp": 1.0},
        {"start": 0.0, "end": 2.0, "midi": 64, "amp": 1.0},
    ]
    labels = [s["chord"] for s in notes_to_chords(am) if s["chord"] != "N"]
    assert labels and labels[0] == "Am", labels

    g7 = [
        {"start": 0.0, "end": 2.0, "midi": 55, "amp": 1.0},
        {"start": 0.0, "end": 2.0, "midi": 59, "amp": 1.0},
        {"start": 0.0, "end": 2.0, "midi": 62, "amp": 1.0},
        {"start": 0.0, "end": 2.0, "midi": 65, "amp": 1.0},
    ]
    labels = [s["chord"] for s in notes_to_chords(g7) if s["chord"] != "N"]
    assert labels and labels[0] == "G7", labels

    mixed = c_notes + [
        {"start": 2.2, "end": 4.2, "midi": 62, "amp": 1.0},
        {"start": 2.2, "end": 4.2, "midi": 66, "amp": 1.0},
        {"start": 2.2, "end": 4.2, "midi": 69, "amp": 1.0},
    ]
    labels = [s["chord"] for s in notes_to_chords(mixed) if s["chord"] != "N"]
    assert "C" in labels and "D" in labels, labels
    print("selftest OK")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", nargs="?")
    ap.add_argument("out_prefix", nargs="?")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        selftest()
        return
    if not args.input or not args.out_prefix:
        ap.error("INPUT and OUT_PREFIX required (or pass --selftest)")

    outs = [args.out_prefix + ext for ext in (".chords.json", ".chords.md")]
    if not args.force and all(os.path.exists(p) and os.path.getsize(p) > 0 for p in outs):
        print(f"[skip] {args.out_prefix}.chords.* already present — pass --force to redo", flush=True)
        return

    t0 = time.time()
    notes = run_basic_pitch(args.input)
    segs = notes_to_chords(notes)
    key = guess_key(notes)
    payload = {
        "engine": "basic-pitch+templates",
        "key": key,
        "notes": notes,
        "segments": segs,
    }
    with open(args.out_prefix + ".chords.json", "w") as f:
        json.dump(payload, f, indent=2)
    with open(args.out_prefix + ".chords.md", "w") as f:
        f.write(render_md(segs, key, len(notes)))
    n_hit = sum(1 for s in segs if s["chord"] != "N")
    print(
        f"[write] {args.out_prefix}.chords.{{json,md}} "
        f"key={key or '—'} chords={n_hit} notes={len(notes)} ({time.time()-t0:.1f}s)",
        flush=True,
    )


if __name__ == "__main__":
    main()
