#!/usr/bin/env python3
"""
diarize_no_hf.py — continuous-window d-vector diarization with NO gated weights.

Uses Resemblyzer, whose encoder weights ship inside the pip package
(`resemblyzer/pretrained.pt`). Nothing is downloaded, no Hugging Face account or
token, and audio never leaves the machine. Install: `pip install resemblyzer`.

Embeds the whole recording as overlapping partial utterances, smooths the
embedding stream, clusters into K speakers, then votes each Whisper segment from
the windows overlapping it.

  python3 diarize_no_hf.py --wav A.wav --segments A.segments.txt --k 3 \
      --out A.clustered.segments.txt --json A.clusters.json

*** READ THIS BEFORE YOU TRUST THE OUTPUT ***

This was measured against ground truth on real far-field
phone recordings and it SCORED WORSE THAN GUESSING — 57.4% vs a 71.3% majority
baseline. Enrolled voiceprints for three different people came out 0.97-0.98
cosine-similar; room reverb and mic distance swamp voice identity, and this
class of encoder is trained on close-talk speech.

So: this script is for close-mic'd or otherwise clean audio. On a phone on a
table in a live room, expect it to fail. ALWAYS score it with `diarize_eval.py`
against some labelled ground truth before shipping attribution from it — never
eyeball the output and call it good. A smooth-looking result is the failure
mode, not the success signal (temporal smoothing alone produces convincing runs
of a single label).

The real fix for attribution is capture-side: two recorders, one per person, and
`diarize_two_mic.py`, which needs no model at all.

Two traps this script already handles, and you must keep handling:
  * `resemblyzer.preprocess_wav()` VAD-trims long silences, which silently
    destroys the mapping back to transcript timestamps. Normalise volume only.
  * average-linkage cosine clustering collapses to one giant cluster plus
    singletons. Spherical k-means on L2-normalised embeddings behaves.
"""
import argparse, json, re, sys
import numpy as np
import soundfile as sf
from resemblyzer import VoiceEncoder, preprocess_wav
from sklearn.cluster import KMeans, SpectralClustering, AgglomerativeClustering
from sklearn.metrics import silhouette_score

TS = re.compile(r"\[(\d+):(\d\d):(\d\d\.\d+)\s*->\s*(\d+):(\d\d):(\d\d\.\d+)\]\s*(.*)")


def parse_segments(path):
    segs = []
    for line in open(path, encoding="utf-8"):
        m = TS.match(line.strip())
        if not m:
            continue
        h1, m1, s1, h2, m2, s2, text = m.groups()
        segs.append({
            "start": int(h1)*3600+int(m1)*60+float(s1),
            "end": int(h2)*3600+int(m2)*60+float(s2),
            "text": text})
    return segs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wav", required=True)
    ap.add_argument("--segments", required=True)
    ap.add_argument("--k", type=int, default=0)
    ap.add_argument("--rate", type=float, default=4.0, help="windows per second")
    ap.add_argument("--smooth", type=int, default=3, help="moving-average span (windows)")
    ap.add_argument("--method", default="kmeans")
    ap.add_argument("--out", required=True)
    ap.add_argument("--json", required=True)
    args = ap.parse_args()

    segs = parse_segments(args.segments)
    # NOTE: resemblyzer's preprocess_wav VAD-trims long silences, which destroys
    # the mapping back to transcript timestamps. Normalise only; keep the clock.
    from resemblyzer.audio import normalize_volume
    from resemblyzer.hparams import audio_norm_target_dBFS, sampling_rate
    wav, sr = sf.read(args.wav, dtype="float32", always_2d=False)
    if wav.ndim > 1:
        wav = wav.mean(axis=1)
    assert sr == sampling_rate, f"expected {sampling_rate} Hz, got {sr}"
    wav = normalize_volume(wav, audio_norm_target_dBFS, increase_only=True)
    print(f"{len(segs)} segments; wav {len(wav)/16000:.1f}s (untrimmed)", file=sys.stderr)

    enc = VoiceEncoder("cpu")
    _, partials, splits = enc.embed_utterance(wav, return_partials=True, rate=args.rate)
    P = np.asarray(partials, dtype=np.float64)
    # window centre times, in seconds, in the preprocessed-wav clock
    centres = np.array([(s.start + s.stop) / 2 / 16000 for s in splits])
    print(f"{len(P)} windows @ rate {args.rate}", file=sys.stderr)

    # temporal smoothing of the embedding stream
    if args.smooth > 1:
        w = args.smooth
        pad = np.pad(P, ((w//2, w//2), (0, 0)), mode="edge")
        P = np.stack([pad[i:i+w].mean(axis=0) for i in range(len(P))])
    P /= np.linalg.norm(P, axis=1, keepdims=True)

    ks = [args.k] if args.k > 0 else list(range(2, 8))
    best = None
    for k in ks:
        if args.method == "spectral":
            aff = (P @ P.T + 1) / 2
            lab = SpectralClustering(n_clusters=k, affinity="precomputed",
                                     random_state=0).fit_predict(aff)
        elif args.method == "agg":
            lab = AgglomerativeClustering(n_clusters=k, metric="cosine",
                                          linkage="average").fit_predict(P)
        else:
            lab = KMeans(n_clusters=k, n_init=20, random_state=0).fit_predict(P)
        try:
            sc = float(silhouette_score(P, lab, metric="cosine"))
        except Exception:
            sc = -1.0
        # temporal coherence of the window stream
        coh = float(np.mean(lab[:-1] == lab[1:]))
        print(f"  k={k} silhouette={sc:.4f} window-coherence={coh:.3f}", file=sys.stderr)
        if best is None or sc > best[0]:
            best = (sc, k, lab)
    sc, k, wlab = best
    print(f"chosen k={k} silhouette={sc:.4f}", file=sys.stderr)

    # vote each transcript segment from its overlapping windows
    rows = []
    for i, s in enumerate(segs):
        sel = (centres >= s["start"]) & (centres <= s["end"])
        if not sel.any():
            j = int(np.argmin(np.abs(centres - (s["start"]+s["end"])/2)))
            sel = np.zeros(len(centres), bool); sel[j] = True
        votes = np.bincount(wlab[sel], minlength=k)
        top = int(np.argmax(votes))
        conf = float(votes[top] / votes.sum())
        rows.append({"i": i, "start": s["start"], "end": s["end"], "text": s["text"],
                     "cluster": top, "conf": conf, "nwin": int(votes.sum())})

    lab = [r["cluster"] for r in rows]
    agree = sum(1 for a, b in zip(rows, rows[1:])
                if b["start"]-a["end"] < 1.5 and a["cluster"] == b["cluster"])
    tot = sum(1 for a, b in zip(rows, rows[1:]) if b["start"]-a["end"] < 1.5)
    runs, cur = [], 1
    for a, b in zip(lab, lab[1:]):
        cur = cur+1 if a == b else (runs.append(cur) or 1)
    runs.append(cur)
    counts = {c: lab.count(c) for c in set(lab)}
    print(f"segment adjacent-agreement {agree}/{tot} = {agree/max(tot,1):.3f} "
          f"(chance {1/k:.2f}); mean run {np.mean(runs):.2f}; sizes {counts}",
          file=sys.stderr)

    json.dump({"k": int(k), "silhouette": sc, "segments": rows},
              open(args.json, "w"), indent=1)
    with open(args.out, "w") as f:
        for r in rows:
            f.write(f"[{r['start']:8.2f} -> {r['end']:8.2f}] "
                    f"[S{r['cluster']} c={r['conf']:.2f}] {r['text']}\n")
    print("wrote", args.out, file=sys.stderr)


if __name__ == "__main__":
    main()
