#!/usr/bin/env python3
"""
structure.py — lyrics + chords -> form map, lyrics.md, chart.md.

Heuristic only (lyric repeats + chord windows). Mark the form ≈.

Usage:
    python3 structure.py OUT_PREFIX [--title TITLE]
    python3 structure.py --selftest

Reads:
    OUT_PREFIX.json          whisper result (segments[].start/end/text)
    OUT_PREFIX.chords.json   chords.py payload

Writes:
    OUT_PREFIX.lyrics.md
    OUT_PREFIX.structure.md
    OUT_PREFIX.chart.md
    OUT_PREFIX.structure.json
"""
from __future__ import annotations

import argparse
import json
import os
import re

def fmt_ts(t):
    t = max(0.0, float(t))
    m = int(t // 60)
    s = t % 60
    return f"{m}:{s:05.2f}"


def norm(text):
    return re.sub(r"[^a-z0-9 ]+", "", (text or "").lower()).strip()


def load_lyrics(whisper_json):
    segs = whisper_json.get("segments") or []
    out = []
    for s in segs:
        text = (s.get("text") or "").strip()
        if not text:
            continue
        out.append({
            "start": float(s.get("start") or 0),
            "end": float(s.get("end") or 0),
            "text": text,
            "norm": norm(text),
        })
    return out


def chorus_sig(lyrics, min_lines=2, max_lines=4):
    """Most-repeated 2–4 line block, or None."""
    lines = [L for L in lyrics if L["norm"]]
    best, best_n = None, 1
    n = len(lines)
    for width in range(max_lines, min_lines - 1, -1):
        counts = {}
        for i in range(0, n - width + 1):
            key = tuple(lines[j]["norm"] for j in range(i, i + width))
            if any(not k for k in key):
                continue
            counts[key] = counts.get(key, 0) + 1
        for key, c in counts.items():
            if c > best_n:
                best, best_n = key, c
        if best_n >= 2:
            return best
    return None


def chords_in(chords, t0, t1):
    labels = []
    for c in chords:
        if c["chord"] == "N":
            continue
        if c["end"] <= t0 or c["start"] >= t1:
            continue
        if not labels or labels[-1] != c["chord"]:
            labels.append(c["chord"])
    return labels


def label_sections(lyrics, chords, duration):
    """Walk the tape and stamp intro/verse/chorus/bridge/outro. ≈ only."""
    sig = chorus_sig(lyrics)
    sections = []
    if duration <= 0:
        duration = max(
            ([L["end"] for L in lyrics] or [0])[-1],
            ([c["end"] for c in chords] or [0])[-1],
            0,
        )
    t0 = 0.0
    if lyrics and lyrics[0]["start"] > 2.0:
        sections.append(_sec("intro", 0.0, lyrics[0]["start"], chords, ""))
        t0 = lyrics[0]["start"]

    i = 0
    verse_n = 0
    chorus_n = 0
    while i < len(lyrics):
        if sig:
            width = len(sig)
            window = tuple(lyrics[j]["norm"] for j in range(i, min(i + width, len(lyrics))))
            if window == sig:
                t1 = lyrics[i + width - 1]["end"]
                chorus_n += 1
                hook = lyrics[i]["text"]
                sections.append(_sec("chorus", lyrics[i]["start"], t1, chords, hook))
                i += width
                t0 = t1
                continue
        # unique stretch until next chorus or end
        j = i + 1
        while j < len(lyrics):
            if sig:
                width = len(sig)
                window = tuple(lyrics[k]["norm"] for k in range(j, min(j + width, len(lyrics))))
                if window == sig:
                    break
            j += 1
        t1 = lyrics[j - 1]["end"]
        hook = lyrics[i]["text"]
        if chorus_n >= 2:
            name = "bridge"
        else:
            verse_n += 1
            name = f"verse-{verse_n}"
        sections.append(_sec(name, lyrics[i]["start"], t1, chords, hook))
        i = j
        t0 = t1

    if duration - t0 > 2.0:
        last = sections[-1]["name"] if sections else ""
        name = "outro" if last.startswith("chorus") or last.startswith("verse") else "outro"
        sections.append(_sec(name, t0, duration, chords, ""))
    if not sections and chords:
        sections.append(_sec("instrumental", 0.0, duration, chords, ""))
    return sections, sig


def _sec(name, t0, t1, chords, hook):
    return {
        "name": name,
        "start": round(t0, 2),
        "end": round(t1, 2),
        "chords": chords_in(chords, t0, t1),
        "hook": hook,
    }


def form_line(sections):
    pretty = []
    for s in sections:
        n = s["name"]
        if n.startswith("verse-"):
            pretty.append("V" + n.split("-")[1])
        elif n == "chorus":
            pretty.append("C")
        elif n == "intro":
            pretty.append("Intro")
        elif n == "bridge":
            pretty.append("Br")
        elif n == "outro":
            pretty.append("Out")
        else:
            pretty.append(n)
    return " – ".join(pretty) if pretty else "—"


def render_lyrics(lyrics):
    lines = ["# Lyrics", ""]
    if not lyrics:
        lines.append("(no sung words detected)")
        lines.append("")
        return "\n".join(lines)
    for L in lyrics:
        lines.append(f"- {fmt_ts(L['start'])}  {L['text']}")
    lines.append("")
    return "\n".join(lines)


def render_structure(sections, key, sig):
    lines = [
        "# Structure",
        "",
        f"Form (≈): {form_line(sections)}",
        f"Key guess: {key or '—'}",
        "",
        "| start | end | section | chords | lyric hook |",
        "| --- | --- | --- | --- | --- |",
    ]
    for s in sections:
        ch = " ".join(s["chords"]) if s["chords"] else "—"
        hook = (s["hook"] or "").replace("|", "/")
        lines.append(
            f"| {fmt_ts(s['start'])} | {fmt_ts(s['end'])} | {s['name']} | {ch} | {hook} |"
        )
    lines.append("")
    lines.append("Form is a lyric-repeat guess. Confirm by ear before trusting a chorus label.")
    lines.append("")
    return "\n".join(lines)


def render_chart(title, lyrics, chords_md, structure_md, sections, key):
    compact = " | ".join(
        f"{s['name']}: {' '.join(s['chords']) or '—'}" for s in sections
    )
    parts = [
        f"# {title}",
        "",
        f"**Form (≈):** {form_line(sections)}",
        f"**Key guess:** {key or '—'}",
        "",
        compact,
        "",
        structure_md.strip(),
        "",
        "## Lyrics",
        "",
    ]
    if lyrics:
        for L in lyrics:
            parts.append(f"- {fmt_ts(L['start'])}  {L['text']}")
    else:
        parts.append("(no sung words detected)")
    parts.append("")
    parts.append(chords_md.strip() if chords_md else "# Chords\n\n(none)")
    parts.append("")
    return "\n".join(parts) + "\n"


def selftest():
    lyrics = [
        {"start": 0.5, "end": 1.0, "text": "hello night", "norm": "hello night"},
        {"start": 1.0, "end": 1.5, "text": "take me home", "norm": "take me home"},
        {"start": 2.0, "end": 2.5, "text": "whoa oh", "norm": "whoa oh"},
        {"start": 2.5, "end": 3.0, "text": "sing it", "norm": "sing it"},
        {"start": 4.0, "end": 4.5, "text": "another verse here", "norm": "another verse here"},
        {"start": 5.0, "end": 5.5, "text": "whoa oh", "norm": "whoa oh"},
        {"start": 5.5, "end": 6.0, "text": "sing it", "norm": "sing it"},
    ]
    chords = [
        {"start": 0.0, "end": 2.0, "chord": "G", "conf": 0.8},
        {"start": 2.0, "end": 4.0, "chord": "C", "conf": 0.8},
        {"start": 4.0, "end": 5.0, "chord": "Em", "conf": 0.8},
        {"start": 5.0, "end": 7.0, "chord": "C", "conf": 0.8},
    ]
    sig = chorus_sig(lyrics)
    assert sig == ("whoa oh", "sing it"), sig
    sections, _ = label_sections(lyrics, chords, 8.0)
    names = [s["name"] for s in sections]
    assert names[0] != "chorus"
    assert "chorus" in names
    assert any(n.startswith("verse") for n in names)
    print("selftest OK")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out_prefix", nargs="?")
    ap.add_argument("--title", default="Song chart")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        selftest()
        return
    if not args.out_prefix:
        ap.error("OUT_PREFIX required (or pass --selftest)")

    wpath = args.out_prefix + ".json"
    cpath = args.out_prefix + ".chords.json"
    whisper = {}
    if os.path.exists(wpath):
        with open(wpath) as f:
            whisper = json.load(f)
    else:
        print(f"[warn] missing {wpath} — lyrics empty", flush=True)
    chords_payload = {"key": None, "segments": []}
    chords_md = ""
    if os.path.exists(cpath):
        with open(cpath) as f:
            chords_payload = json.load(f)
        md_path = args.out_prefix + ".chords.md"
        if os.path.exists(md_path):
            with open(md_path) as f:
                chords_md = f.read()
    else:
        print(f"[warn] missing {cpath} — chords empty", flush=True)

    lyrics = load_lyrics(whisper)
    duration = 0.0
    if lyrics:
        duration = lyrics[-1]["end"]
    if chords_payload.get("segments"):
        duration = max(duration, chords_payload["segments"][-1]["end"])
    sections, sig = label_sections(lyrics, chords_payload.get("segments") or [], duration)
    key = chords_payload.get("key")
    structure_md = render_structure(sections, key, sig)
    lyrics_md = render_lyrics(lyrics)
    chart_md = render_chart(args.title, lyrics, chords_md, structure_md, sections, key)
    payload = {"key": key, "form": form_line(sections), "sections": sections}

    with open(args.out_prefix + ".lyrics.md", "w") as f:
        f.write(lyrics_md)
    with open(args.out_prefix + ".structure.md", "w") as f:
        f.write(structure_md)
    with open(args.out_prefix + ".structure.json", "w") as f:
        json.dump(payload, f, indent=2)
    with open(args.out_prefix + ".chart.md", "w") as f:
        f.write(chart_md)
    print(
        f"[write] {args.out_prefix}.{{lyrics,structure,chart}}.md form={payload['form']}",
        flush=True,
    )


if __name__ == "__main__":
    main()
