#!/usr/bin/env python3
"""
diarize_eval.py — score a diarization run against ground truth, so you find out
whether attribution actually works BEFORE you write it into anyone's note.

This exists because on 2026-07-31 a diarization pass looked convincing, read
plausibly, and was worse than guessing. Eyeballing diarization output does not
work: temporal smoothing alone produces long, believable runs of a single
speaker label. The only honest check is a score against labels.

Ground truth comes from an already-attributed `transcript.md` — the cleaned
transcript carries `**NAME:**` turn labels but no timestamps, while the
`.segments.txt` carries timestamps but no labels. This script aligns the two by
global token alignment (difflib), which survives the heavy editing a cleaned
transcript has been through, then compares against a diarization JSON.

  python3 diarize_eval.py --segments A.segments.txt --transcript A/transcript.md \
      --clusters A.clusters.json

Reports a confusion matrix, the best cluster→speaker mapping accuracy, and the
majority-class baseline.

THE BAR: if accuracy does not clearly beat the majority baseline, the
diarization carries no usable speaker signal. Throw it away. Do not ship
"best-effort" attribution off the back of it — an unattributed line is honest,
a wrongly attributed one puts words in a real person's mouth.
"""
import argparse, itertools, json, re, sys
from collections import defaultdict

TS = re.compile(r"\[(\d+):(\d\d):(\d\d\.\d+)\s*->\s*(\d+):(\d\d):(\d\d\.\d+)\]\s*(.*)")
TURN = re.compile(r"^\*\*([A-Z][A-Za-z ]*):\*\*\s*(.*)")
SKIP = {"SPEAKER", "ATTRIBUTION NOTE"}


def norm_tokens(s):
    s = re.sub(r"\[[^\]]*\]", " ", s.lower())
    s = re.sub(r"[^a-z0-9' ]+", " ", s)
    return [t for t in s.split() if t]


def parse_segments(path):
    out = []
    for line in open(path, encoding="utf-8"):
        m = TS.match(line.strip())
        if m:
            h1, m1, s1, h2, m2, s2, text = m.groups()
            out.append({"start": int(h1)*3600+int(m1)*60+float(s1),
                        "end": int(h2)*3600+int(m2)*60+float(s2),
                        "tok": norm_tokens(text)})
    return out


def parse_turns(path):
    out = []
    for line in open(path, encoding="utf-8"):
        m = TURN.match(line.strip())
        if m:
            spk, text = m.groups()
            spk = spk.strip().upper()
            if spk not in SKIP:
                out.append({"spk": spk, "tok": norm_tokens(text)})
    return out


def ground_truth(segments_path, transcript_path, purity=0.8):
    """Map labelled transcript turns onto timestamped segments."""
    import difflib
    segs, turns = parse_segments(segments_path), parse_turns(transcript_path)

    seg_stream, seg_owner = [], []
    for i, s in enumerate(segs):
        for t in s["tok"]:
            seg_stream.append(t); seg_owner.append(i)
    tr_stream, tr_spk = [], []
    for t in turns:
        for w in t["tok"]:
            tr_stream.append(w); tr_spk.append(t["spk"])

    sm = difflib.SequenceMatcher(None, seg_stream, tr_stream, autojunk=False)
    votes = defaultdict(lambda: defaultdict(int))
    for a, b, n in sm.get_matching_blocks():
        for d in range(n):
            votes[seg_owner[a+d]][tr_spk[b+d]] += 1

    truth = {}
    for si, v in votes.items():
        tot = sum(v.values())
        spk, n = max(v.items(), key=lambda kv: kv[1])
        # trust a segment only if its tokens came overwhelmingly from one
        # speaker AND the alignment actually covered most of the segment
        if n / tot >= purity and tot >= max(3, 0.6 * len(segs[si]["tok"])):
            truth[si] = spk
    return truth, segs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--segments", required=True)
    ap.add_argument("--transcript", required=True, help="a transcript.md WITH **NAME:** labels")
    ap.add_argument("--clusters", required=True, help="json from diarize_no_hf.py")
    a = ap.parse_args()

    truth, segs = ground_truth(a.segments, a.transcript)
    print(f"ground truth: {len(truth)} of {len(segs)} segments labelled")
    if len(truth) < 50:
        print("!! too little ground truth to conclude anything", file=sys.stderr)

    pred = {s["i"]: s["cluster"] for s in json.load(open(a.clusters))["segments"]}
    pairs = [(truth[i], pred[i]) for i in truth if i in pred]
    if not pairs:
        sys.exit("no overlap between ground truth and predictions")

    M = defaultdict(lambda: defaultdict(int))
    for t, c in pairs:
        M[t][c] += 1
    spks, cls = sorted(M), sorted({c for _, c in pairs})

    print(f"\nevaluated {len(pairs)} segments\n")
    print(" " * 10 + "".join(f"  S{c:<5}" for c in cls))
    for s in spks:
        print(f"{s:<10}" + "".join(f"{M[s][c]:7d}" for c in cls))

    best = 0
    for perm in itertools.permutations(cls, min(len(spks), len(cls))):
        best = max(best, sum(M[s][perm[i]] for i, s in enumerate(spks[:len(perm)])))
    baseline = max(sum(M[s].values()) for s in spks)
    n = len(pairs)
    print(f"\nbest cluster->speaker accuracy : {best}/{n} = {best/n:.3f}")
    print(f"majority-class baseline        : {baseline}/{n} = {baseline/n:.3f}")

    if best <= baseline:
        print("\nVERDICT: WORSE THAN GUESSING. No usable speaker signal — "
              "discard this diarization and leave the turns unattributed.")
    elif best < baseline + 0.10 * n:
        print("\nVERDICT: marginal. Barely beats the baseline; not safe for "
              "per-person attribution.")
    else:
        print("\nVERDICT: usable. Still label attribution as probable, not certain.")


if __name__ == "__main__":
    main()
