#!/usr/bin/env python3
"""
diarize_two_mic.py — speaker separation from two lav recorders of one meeting.

Premise: each person wears their own mic, so each recorder is LOUDEST for its
wearer. We:
  1. Compute a short-window energy envelope for each recorder.
  2. Cross-correlate the envelopes to recover the start-time offset between the
     two devices (they rarely start at the same instant).
  3. After aligning, label each time window by whichever mic is louder
     (with a ratio threshold + smoothing) -> a speaker timeline.
  4. Map that timeline onto the SPINE recorder's transcript segments, tagging
     each line with the speaker name.

The spine recorder is the one whose transcript we keep; the timeline is in the
spine's own clock, so the tags line up with the spine's timestamps.

Usage:
    python3 diarize_two_mic.py \
        --spine A.WAV --other B.WAV \
        --spine-segments A.segments.txt \
        --name-spine "Dana" --name-other "Rae" \
        --out A.attributed.segments.txt [--timeline A.timeline.json]

Prints the recovered offset (a good correctness check: it should match the
difference in the two filenames' start timestamps).
"""
import argparse, json, re, sys
import numpy as np
import soundfile as sf

HOP_S = 0.05          # 50 ms analysis windows
SMOOTH_WIN = 11       # median-filter span (~0.55 s) to debounce speaker flips
RATIO_DB = 3.0        # a mic must be this many dB louder to "win" the window


def envelope(path, hop_s=HOP_S):
    audio, sr = sf.read(path, dtype="float32", always_2d=False)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    hop = int(sr * hop_s)
    n = len(audio) // hop
    frames = audio[: n * hop].reshape(n, hop)
    rms = np.sqrt(np.mean(frames.astype(np.float64) ** 2, axis=1) + 1e-12)
    return rms.astype(np.float64), hop_s


def recover_lag(env_a, env_b):
    """Frames to shift env_b so it aligns with env_a (positive => b starts later)."""
    a = env_a - env_a.mean()
    b = env_b - env_b.mean()
    from scipy.signal import fftconvolve
    corr = fftconvolve(a, b[::-1], mode="full")
    lag = np.argmax(corr) - (len(b) - 1)
    return int(lag)


def median_filter(x, k):
    if k <= 1:
        return x
    pad = k // 2
    xp = np.pad(x, pad, mode="edge")
    return np.array([np.median(xp[i : i + k]) for i in range(len(x))])


def parse_ts(s):
    h, m, sec = s.split(":")
    return int(h) * 3600 + int(m) * 60 + float(sec)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spine", required=True)
    ap.add_argument("--other", required=True)
    ap.add_argument("--spine-segments", required=True)
    ap.add_argument("--name-spine", default="SPEAKER_A")
    ap.add_argument("--name-other", default="SPEAKER_B")
    ap.add_argument("--out", required=True)
    ap.add_argument("--timeline", default=None)
    args = ap.parse_args()

    env_s, hop = envelope(args.spine)
    env_o, _ = envelope(args.other)

    lag = recover_lag(env_s, env_o)   # frames; shift `other` by +lag to match spine
    print(f"[align] recovered offset: {lag * hop:+.1f}s (spine - other start). "
          f"other {'starts later' if lag > 0 else 'starts earlier'}.", flush=True)

    # Put `other` onto the spine's frame grid.
    o_on_s = np.zeros_like(env_s)
    for i in range(len(env_s)):
        j = i - lag
        if 0 <= j < len(env_o):
            o_on_s[i] = env_o[j]

    # dB comparison per frame, smoothed
    s_db = 20 * np.log10(env_s + 1e-9)
    o_db = 20 * np.log10(o_on_s + 1e-9)
    diff = median_filter(s_db - o_db, SMOOTH_WIN)

    # speaker per frame: +1 spine, -1 other, 0 unclear (carry previous)
    spk = np.zeros(len(diff), dtype=int)
    cur = 1
    for i, d in enumerate(diff):
        if d > RATIO_DB:
            cur = 1
        elif d < -RATIO_DB:
            cur = -1
        spk[i] = cur

    def who(v):
        return args.name_spine if v == 1 else args.name_other

    # speaker timeline (merged runs)
    timeline = []
    start = 0
    for i in range(1, len(spk) + 1):
        if i == len(spk) or spk[i] != spk[start]:
            timeline.append({"start": round(start * hop, 2),
                             "end": round(i * hop, 2),
                             "speaker": who(spk[start])})
            start = i
    if args.timeline:
        json.dump(timeline, open(args.timeline, "w"), indent=2)

    def speaker_for(t0, t1):
        i0, i1 = int(t0 / hop), max(int(t1 / hop), int(t0 / hop) + 1)
        seg = spk[i0:i1]
        if len(seg) == 0:
            return args.name_spine
        return args.name_spine if seg.sum() >= 0 else args.name_other

    # attribute spine transcript segments
    line_re = re.compile(r"\[(\d\d:\d\d:[\d.]+) -> (\d\d:\d\d:[\d.]+)\]\s*(.*)")
    out_lines, n = [], 0
    for raw in open(args.spine_segments):
        m = line_re.match(raw.strip())
        if not m:
            continue
        a, b, text = m.group(1), m.group(2), m.group(3)
        sp = speaker_for(parse_ts(a), parse_ts(b))
        out_lines.append(f"[{a} -> {b}] {sp}: {text}")
        n += 1
    open(args.out, "w").write("\n".join(out_lines) + "\n")
    print(f"[diarize] wrote {n} attributed segments -> {args.out}", flush=True)


if __name__ == "__main__":
    main()
