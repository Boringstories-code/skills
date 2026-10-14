#!/usr/bin/env python3
"""
diarize_n_mic.py — speaker separation from N per-person recorders of one meeting.

Generalizes diarize_two_mic.py from 2 recorders to any number. Same premise:
each person carries their own recorder (phone in a shirt pocket is enough), so
each recorder is LOUDEST for its owner. We:

  1. Compute a short-window energy envelope for each recorder.
  2. Cross-correlate each recorder's envelope against the SPINE's to recover the
     start-time offset (devices never start together), then resample onto the
     spine's frame grid.
  3. Per frame, pick the loudest recorder — but only if it beats the runner-up by
     a margin. Otherwise the frame is UNCLEAR.
  4. Map that timeline onto the spine's transcript segments.

WHY THE MARGIN AND THE UNCLEAR LABEL MATTER
-------------------------------------------
The failure mode of every diarizer is a smooth, plausible-looking result that is
wrong. This engine's own measured history is the cautionary tale: acoustic
diarization on far-field phone audio scored 57.4% against a 71.3% majority
baseline — worse than guessing — and a 2-speaker file *looked* like a clean 85%
split that was really just temporal smoothing.

So this script refuses to fill silence with confidence. A frame where nobody
clearly wins is labeled UNCLEAR, not handed to whoever spoke last. An unlabeled
line is honest; a wrongly labeled one puts words in a real person's mouth and
then propagates into a private note about them. Tune with --margin-db; raise it
to attribute less and be righter.

Per-person recorders make this tractable in a way single-mic separation is not:
we are comparing the SAME voice across microphones, not trying to tell two
voices apart. Reverb and mic distance sink voiceprints; they do not sink "which
pocket is this coming from."

Usage:
    python3 diarize_n_mic.py \
        --rec Alice=alice.wav --rec Bob=bob.wav --rec Carol=carol.wav \
        --spine the owner \
        --spine-segments owner.segments.txt \
        --out attributed.segments.txt \
        [--timeline timeline.json] [--margin-db 4] [--report]

--spine defaults to the first --rec. The spine's transcript is the one that gets
attributed, so make it the cleanest recording (usually the loudest talker's, or
whichever device didn't clip).

Sanity check on the output: the printed offsets should roughly match the
difference in the recordings' real start times. A wild offset means the
cross-correlation latched onto the wrong peak — usually too little shared audio.
"""
import argparse, json, re, sys
import numpy as np
import soundfile as sf

HOP_S = 0.05          # 50 ms analysis windows
SMOOTH_WIN = 11       # median-filter span (~0.55 s) to debounce speaker flips
MARGIN_DB = 4.0       # winner must beat runner-up by this many dB
UNCLEAR = "SPEAKER"   # label for frames/segments with no clear winner


def envelope(path, hop_s=HOP_S):
    audio, sr = sf.read(path, dtype="float32", always_2d=False)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    hop = int(sr * hop_s)
    n = len(audio) // hop
    if n == 0:
        raise SystemExit(f"[error] {path}: too short to analyze")
    frames = audio[: n * hop].reshape(n, hop)
    rms = np.sqrt(np.mean(frames.astype(np.float64) ** 2, axis=1) + 1e-12)
    return rms.astype(np.float64)


def onset_strength(env):
    """Half-wave-rectified derivative of the log envelope, z-scored.

    Aligning on ONSETS rather than raw energy matters. A conversation's energy
    envelope is a broad step function, so its autocorrelation peak is broad and
    the argmax drifts — measured on synthetic 3-recorder audio, raw-envelope
    correlation recovered -7.2s for a true +1.2s offset, and every downstream
    label inherited the error. Onsets are sharp and near-unique in time, so the
    correlation peak is a spike.
    """
    log_env = np.log(env + 1e-9)
    d = np.diff(log_env, prepend=log_env[0])
    d = np.maximum(d, 0.0)
    s = d.std()
    return (d - d.mean()) / s if s > 1e-12 else d - d.mean()


def recover_lag(env_ref, env_other, max_lag_frames=None):
    """Frames to index-shift env_other onto env_ref's grid: grid[i] = env_other[i - lag].

    SIGN CONVENTION — the easy thing to get backwards. A NEGATIVE lag means the
    other recorder's content arrives LATER than the spine's (it started recording
    earlier, so its audio sits further into the file). Callers reporting a
    human-readable offset want `delay = -lag * HOP_S`.

    Returns (lag, confidence) where confidence is the normalized correlation peak
    over the runner-up outside its immediate neighbourhood — a flat ratio near 1.0
    means the alignment is not trustworthy and should be reported, not hidden.
    """
    from scipy.signal import fftconvolve
    a = onset_strength(env_ref)
    b = onset_strength(env_other)
    corr = fftconvolve(a, b[::-1], mode="full")
    zero = len(b) - 1
    if max_lag_frames is not None:
        lo = max(0, zero - max_lag_frames)
        hi = min(len(corr), zero + max_lag_frames + 1)
        window = corr[lo:hi]
        peak_i = int(np.argmax(window)) + lo
    else:
        window = corr
        peak_i = int(np.argmax(corr))
    peak = corr[peak_i]

    # Confidence: peak vs the best competing peak at least 1s away.
    guard = int(1.0 / HOP_S)
    masked = np.array(corr, dtype=np.float64)
    m_lo = max(0, peak_i - guard)
    m_hi = min(len(masked), peak_i + guard + 1)
    masked[m_lo:m_hi] = -np.inf
    if max_lag_frames is not None:
        runner = masked[max(0, zero - max_lag_frames):min(len(masked), zero + max_lag_frames + 1)]
    else:
        runner = masked
    runner = runner[np.isfinite(runner)]
    second = float(runner.max()) if runner.size else 0.0
    conf = float(peak / second) if second > 1e-12 else float("inf")
    return int(peak_i - zero), conf


def median_filter(x, k):
    if k <= 1:
        return x
    pad = k // 2
    xp = np.pad(x, pad, mode="edge")
    return np.array([np.median(xp[i : i + k]) for i in range(len(x))])


def parse_ts(s):
    h, m, sec = s.split(":")
    return int(h) * 3600 + int(m) * 60 + float(sec)


def fmt_hms(t):
    h = int(t // 3600); m = int((t % 3600) // 60); s = t % 60
    return f"{h:02d}:{m:02d}:{s:05.2f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rec", action="append", required=True, metavar="NAME=PATH",
                    help="one per recorder, e.g. --rec the owner=owner.wav (repeatable)")
    ap.add_argument("--spine", default=None,
                    help="name of the recorder whose transcript is being attributed "
                         "(default: the first --rec)")
    ap.add_argument("--spine-segments", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--timeline", default=None)
    ap.add_argument("--margin-db", type=float, default=MARGIN_DB,
                    help=f"winner must beat runner-up by this many dB (default {MARGIN_DB}); "
                         "raise to attribute less and be righter")
    ap.add_argument("--smooth", type=int, default=SMOOTH_WIN)
    ap.add_argument("--max-lag", type=float, default=300.0,
                    help="only search offsets within +/- this many seconds (default 300; "
                         "0 disables the limit). Recorders started within a few minutes of "
                         "each other should never need more.")
    ap.add_argument("--min-align-conf", type=float, default=1.5,
                    help="warn when the alignment peak is less than this many times the "
                         "best competing peak (default 1.5)")
    ap.add_argument("--unclear-label", default=UNCLEAR)
    ap.add_argument("--report", action="store_true",
                    help="print per-speaker talk time and the unclear fraction")
    args = ap.parse_args()

    names, paths = [], []
    for spec in args.rec:
        if "=" not in spec:
            raise SystemExit(f"[error] --rec expects NAME=PATH, got: {spec}")
        n, p = spec.split("=", 1)
        if n in names:
            raise SystemExit(f"[error] duplicate recorder name: {n}")
        names.append(n); paths.append(p)

    if len(names) < 2:
        raise SystemExit("[error] need at least two recorders; for one recorder "
                         "use diarize_no_hf.py and score it with diarize_eval.py")

    spine = args.spine or names[0]
    if spine not in names:
        raise SystemExit(f"[error] --spine {spine!r} is not one of: {', '.join(names)}")
    si = names.index(spine)

    envs = [envelope(p) for p in paths]
    ref = envs[si]
    n_frames = len(ref)

    # Align every recorder onto the spine's frame grid.
    grid = np.zeros((len(names), n_frames), dtype=np.float64)
    for k, env in enumerate(envs):
        if k == si:
            grid[k] = ref
            continue
        max_lag_frames = int(args.max_lag / HOP_S) if args.max_lag > 0 else None
        lag, conf = recover_lag(ref, env, max_lag_frames)
        warn = "" if conf >= args.min_align_conf else "  ** LOW CONFIDENCE — check this **"
        delay = -lag * HOP_S   # see recover_lag: negative lag => content arrives later
        print(f"[align] {names[k]:>12}: content sits {delay:+.1f}s vs spine "
              f"({spine}) — {names[k]} {'started recording earlier' if delay > 0 else 'started recording later'}"
              f"  [peak/runner-up {conf:.2f}]{warn}", flush=True)
        if warn:
            print(f"[align] {names[k]}: alignment is not trustworthy. Sanity-check it against the "
                  f"recordings' real start times before believing any attribution derived from it.",
                  flush=True)
        idx = np.arange(n_frames) - lag
        valid = (idx >= 0) & (idx < len(env))
        grid[k, valid] = env[idx[valid]]

    db = 20 * np.log10(grid + 1e-9)
    db = np.vstack([median_filter(db[k], args.smooth) for k in range(len(names))])

    order = np.argsort(db, axis=0)
    best = order[-1]
    runner = order[-2]
    top = db[best, np.arange(n_frames)]
    second = db[runner, np.arange(n_frames)]
    clear = (top - second) >= args.margin_db

    spk = np.where(clear, best, -1)   # -1 => unclear

    def who(v):
        return names[v] if v >= 0 else args.unclear_label

    # Merged-run timeline
    timeline, start = [], 0
    for i in range(1, n_frames + 1):
        if i == n_frames or spk[i] != spk[start]:
            timeline.append({"start": round(start * HOP_S, 2),
                             "end": round(i * HOP_S, 2),
                             "speaker": who(spk[start])})
            start = i
    if args.timeline:
        json.dump(timeline, open(args.timeline, "w"), indent=2)

    def speaker_for(t0, t1):
        """Majority vote across the segment; unclear unless a real speaker wins outright."""
        i0 = int(t0 / HOP_S)
        i1 = max(int(t1 / HOP_S), i0 + 1)
        seg = spk[i0:i1]
        if len(seg) == 0:
            return args.unclear_label
        counts = np.bincount(seg[seg >= 0], minlength=len(names)) if (seg >= 0).any() else None
        if counts is None or counts.max() <= len(seg) / 2:
            return args.unclear_label
        return names[int(counts.argmax())]

    line_re = re.compile(r"\[(\d\d:\d\d:[\d.]+) -> (\d\d:\d\d:[\d.]+)\]\s*(.*)")
    out_lines, n, tally = [], 0, {}
    for raw in open(args.spine_segments):
        m = line_re.match(raw.strip())
        if not m:
            continue
        a, b, text = m.group(1), m.group(2), m.group(3)
        sp = speaker_for(parse_ts(a), parse_ts(b))
        out_lines.append(f"[{a} -> {b}] {sp}: {text}")
        tally[sp] = tally.get(sp, 0) + 1
        n += 1
    open(args.out, "w").write("\n".join(out_lines) + "\n")
    print(f"[diarize] wrote {n} attributed segments -> {args.out}", flush=True)

    if args.report or True:
        unclear = tally.get(args.unclear_label, 0)
        print(f"[report] segments by speaker (margin {args.margin_db} dB):", flush=True)
        for name in names + [args.unclear_label]:
            c = tally.get(name, 0)
            if c:
                print(f"           {name:>12}: {c:5d}  ({100.0 * c / max(n, 1):5.1f}%)", flush=True)
        print(f"[report] attributed {100.0 * (n - unclear) / max(n, 1):.1f}% of segments. "
              f"Raise --margin-db to attribute less and be righter; lower it to "
              f"attribute more and risk putting words in the wrong mouth.", flush=True)


if __name__ == "__main__":
    main()
