#!/usr/bin/env python3
"""quality_bar.py — the release gate (ticket 11): Private mode vs Agent mode on real sittings.

    python3 scripts/quality_bar.py SITTING_DIR [SITTING_DIR ...] [--out report.md] [--no-clean]
    MEETING_LOOP_RAM_GB=8 python3 scripts/quality_bar.py ...      (the 8 GB run)

Each SITTING_DIR holds the sitting's transcript file(s) (*.txt / *.md, read in name order as
one sitting, like `process` does) and `agent-items.json`: Agent mode's items for that
sitting ({"action_items": [{task, quote}]} or a bare list). Both sides pass the same
quote check. A Private item "catches" an Agent item when their quotes land within
MATCH_WINDOW transcript lines of each other. Invented = Private items the quote check
dropped (never shipped; counted so the prompt can be tuned). Exit 0 on PASS, 1 on FAIL.

The line window is a quick check, not the gate: on a dense sitting, cue lines picked at random
land near most Agent items too, so the report prints that chance level and the precision. The
gate is a judge's call, item by item, on whether a Private item names the same to-do:

    python3 scripts/quality_bar.py --judged judge-16gb.json [--judged judge-8gb.json]

Each verdict file is written by an independent judge model following quality_bar_judge.md
(beside this script) over one run's private-items.json. PASS: judged catch >= PASS_RATE.
BETA: >= BETA_RATE, so Private mode ships labeled as a beta. Either needs noise <= NOISE_CAP.
Exit 0 on PASS or BETA, 1 on FAIL.

Internal tool: not in release.json, so it never ships.
"""
import argparse
import json
import random
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import local_model  # noqa: E402
import meeting_loop as ml  # noqa: E402

PASS_RATE = 0.80
MATCH_WINDOW = 2  # lines; the two modes often quote neighboring lines of one commitment
# Beta bars, set at the level Private mode reached on 2026-10-07 (judged 73-78% on 16 GB, about
# 71% on 8 GB; noise 48% and 60% of the list): a guard against slipping back, not a quality claim.
BETA_RATE = 0.70
NOISE_CAP = 2 / 3  # share of Private items judged not to be to-dos at all (repeats are counted apart)
AGENT_ITEMS = "agent-items.json"


def load_sitting(folder):
    """-> (name, transcript lines, agent items) for one sitting folder."""
    folder = Path(folder)
    files = sorted(p for p in folder.iterdir() if p.suffix.lower() in ml.TRANSCRIPT_EXTS)
    if not files:
        raise ml.RunError(f"{folder}: no transcript (*.txt / *.md); run `meeting-loop transcribe` first")
    if not (folder / AGENT_ITEMS).is_file():
        raise ml.RunError(f"{folder}: no {AGENT_ITEMS}")
    lines = [l for f in files for l in ml.load_transcript(f)]
    agent = json.loads((folder / AGENT_ITEMS).read_text())
    return folder.name, lines, agent["action_items"] if isinstance(agent, dict) else agent


def match(agent_items, private_items, lines):
    """-> (caught agent items, missed agent items, private items matching no agent item).
    Each Private item catches at most one Agent item: the nearest unused one in the window."""
    def where(it):
        return it["at"] if isinstance(it.get("at"), int) else ml._find_line_index(it["quote"], lines)
    pidx = [where(p) for p in private_items]
    caught, missed, used = [], [], set()
    for a in agent_items:
        ai = where(a)
        near = [(abs(pi - ai), n) for n, pi in enumerate(pidx)
                if n not in used and None not in (ai, pi) and abs(pi - ai) <= MATCH_WINDOW]
        if near:
            used.add(min(near)[1])
            caught.append(a)
        else:
            missed.append(a)
    return caught, missed, [p for n, p in enumerate(private_items) if n not in used]


def chance(agent_items, n, lines, trials=200):
    """Average catch for n CUE lines picked at random: what listing volume alone would score."""
    tagged = [i for i, l in enumerate(lines) if ml.CUE.search(l["text"])]
    rng = random.Random(0)
    picks = lambda: [{"at": i, "quote": lines[i]["text"]} for i in rng.sample(tagged, min(n, len(tagged)))]
    return sum(len(match(agent_items, picks(), lines)[0]) for _ in range(trials)) / trials


def run_sitting(name, lines, agent_items, model, clean):
    """One sitting through both modes -> a result dict (counts, timings, item lists)."""
    agent_kept, agent_dropped = ml.quote_check([dict(i) for i in agent_items], lines)
    t = time.time()
    if clean:
        ml.clean_lines(lines, model)
    t_clean = time.time() - t
    t = time.time()
    synth = ml.synthesize_local(lines, model)
    t_synth = time.time() - t
    private_kept, invented = ml.quote_check(synth["action_items"], lines)
    caught, missed, extra = match(agent_kept, private_kept, lines)
    return {"name": name, "lines": len(lines), "chars": sum(len(l["line"]) for l in lines),
            "agent": len(agent_kept), "agent_dropped": agent_dropped, "private": len(private_kept),
            "private_items": private_kept,
            "caught": caught, "missed": missed, "extra": extra, "invented": invented,
            "chance": chance(agent_kept, len(private_kept), lines),
            "clean_secs": t_clean if clean else None, "synth_secs": t_synth, "note": synth.get("note")}


def _pct(n, d):
    return f"{n / d:.0%}" if d else "n/a"


def report(results, choice, load_secs):
    caught = sum(len(r["caught"]) for r in results)
    agent = sum(r["agent"] for r in results)
    rate = caught / agent if agent else 0.0
    passed = agent > 0 and rate >= PASS_RATE
    private = sum(r["private"] for r in results)
    precise = private - sum(len(r["extra"]) for r in results)
    luck = sum(r["chance"] for r in results)
    out = [f"# Private mode quality bar — {'PASS' if passed else 'FAIL'}", "",
           f"- Model: `{choice['model']}`{' (8 GB path)' if choice['low_ram'] else ''}; load {ml._clock(load_secs)}",
           f"- Catch rate: **{caught}/{agent} = {_pct(caught, agent)}** (bar {PASS_RATE:.0%}, "
           f"match window ±{MATCH_WINDOW} lines)",
           f"- Precision: **{precise}/{private} = {_pct(precise, private)}** of Private items match an Agent "
           f"item; chance level (the same number of cue lines picked at random) catches {luck:.1f}/{agent}",
           f"- Invented shipped: **0** (quote check); invented caught and dropped: "
           f"{sum(r['invented'] for r in results)}", ""]
    notes = {r["note"] for r in results if r["note"]}
    if notes:
        out += [f"- Note shown: {n}" for n in notes] + [""]
    out += ["| Sitting | Lines | Agent | Private | Caught | Rate | Invented dropped | Cleanup | Synthesis |",
            "|---|---|---|---|---|---|---|---|---|"]
    for r in results:
        clean = ml._clock(r["clean_secs"]) if r["clean_secs"] is not None else "off"
        out.append(f"| {r['name']} | {r['lines']} | {r['agent']} | {r['private']} | {len(r['caught'])} | "
                   f"{_pct(len(r['caught']), r['agent'])} | {r['invented']} | {clean} | {ml._clock(r['synth_secs'])} |")
    for r in results:
        out += ["", f"## {r['name']}", ""]
        if r["agent_dropped"]:
            out.append(f"- Agent items dropped by the quote check (not counted): {r['agent_dropped']}")
        out += [f"- MISSED: {a['task']} — \"{a['quote']}\"" for a in r["missed"]]
        out += [f"- Private only: {p['task']} — \"{p['quote']}\"" for p in r["extra"]]
        if not (r["missed"] or r["extra"] or r["agent_dropped"]):
            out.append("- Every Agent item caught; nothing extra.")
    return "\n".join(out) + "\n", passed


def judged_verdict(verdicts):
    """A judge's verdicts {sitting: {agent_counted, caught, private_total, noise, ...}} ->
    (report text, "PASS" | "BETA" | "FAIL")."""
    total = lambda key: sum(v.get(key, 0) for v in verdicts.values())
    agent, caught, private, noise = (total(k) for k in ("agent_counted", "caught", "private_total", "noise"))
    rate, noise_share = (caught / agent if agent else 0.0), (noise / private if private else 0.0)
    quiet = noise_share <= NOISE_CAP
    verdict = "PASS" if rate >= PASS_RATE and quiet else "BETA" if rate >= BETA_RATE and quiet else "FAIL"
    out = [f"# Private mode, judged — {verdict}", "",
           f"- Judged catch: **{caught}/{agent} = {_pct(caught, agent)}** (release {PASS_RATE:.0%}, beta {BETA_RATE:.0%})",
           f"- Noise: **{noise}/{private} = {_pct(noise, private)}** of Private items (cap {NOISE_CAP:.0%}); "
           f"repeats {total('duplicate')}, real extras {total('real_extra')}", "",
           "| Sitting | Caught | Rate | Private | Noise | Repeats |", "|---|---|---|---|---|---|"]
    out += [f"| {name} | {v.get('caught', 0)}/{v.get('agent_counted', 0)} | {_pct(v.get('caught', 0), v.get('agent_counted', 0))} "
            f"| {v.get('private_total', 0)} | {v.get('noise', 0)} | {v.get('duplicate', 0)} |" for name, v in verdicts.items()]
    for name, v in verdicts.items():
        out += [f"- MISSED ({name}): {m}" for m in v.get("misses", [])]
    return "\n".join(out) + "\n", verdict


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("sittings", nargs="*", metavar="SITTING_DIR")
    p.add_argument("--judged", action="append", metavar="VERDICT_JSON",
                   help="gate on a judge's verdict file instead (see quality_bar_judge.md); repeatable")
    p.add_argument("--out", help="also write the report here")
    p.add_argument("--no-clean", dest="clean", action="store_false", default=None,
                   help="skip timing cleanup (default: on for 16 GB+, off on the 8 GB path)")
    args = p.parse_args(argv)
    if args.judged:
        verdicts = [judged_verdict(json.loads(Path(f).read_text())) for f in args.judged]
        for f, (text, _) in zip(args.judged, verdicts):
            print(f"<!-- {f} -->\n{text}")
        return 0 if all(v != "FAIL" for _, v in verdicts) else 1
    if not args.sittings:
        p.error("give SITTING_DIR(s), or --judged VERDICT_JSON")
    try:
        sittings = [load_sitting(s) for s in args.sittings]
        choice = local_model.choose_model()
        clean = (not choice["low_ram"]) if args.clean is None else args.clean
        model = ml.LocalModel(choice)
        try:
            results = [run_sitting(*s, model, clean) for s in sittings]
            load_secs = model._session.loaded if model._session else 0.0
        finally:
            model.close()
    except ml.RunError as e:
        print(f"quality-bar: {e}", file=sys.stderr)
        return 2
    for folder, r in zip(args.sittings, results):  # for eyeballing what Private mode found
        (Path(folder) / "private-items.json").write_text(json.dumps(r["private_items"], indent=1) + "\n")
    text, passed = report(results, choice, load_secs)
    print(text)
    if args.out:
        Path(args.out).write_text(text)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
