#!/usr/bin/env python3
"""Concept-card tooling for the understanding layer (00-OS/wiki/concepts/).

  concepts.py lint  <file|dir> ...        gate: exit 1 if any card fails the mechanical checks
  concepts.py graph [dir]                 every typed edge as TSV: from  type  to  source
  concepts.py brief-data [dir] [--since N] seed for the weekly brief: convergence / contested / gaps / stubs / orphans
  concepts.py stage --kind K --slug S [--file F]   copy a message/video/note into 00-OS/raw/messages/ with provenance
  concepts.py index [dir]                 regenerate "## Cards by topic" in _index.md from card frontmatter (deterministic)
  concepts.py selftest                    the one runnable check

stdlib + PyYAML (already installed). Run from the vault root.
"""
import argparse, datetime as dt, os, re, sys, tempfile
from pathlib import Path
import yaml

EDGE_TYPES = {"causes", "enables", "requires", "contradicts", "generalizes", "instance-of", "predicts", "cost-of"}
CONFIDENCE = {"low", "medium", "high"}
STATUS = {"forming", "held", "contested", "retired"}
SECTIONS = ["Claim", "Mechanism", "Evidence", "Connections", "Open questions", "So what", "Contradictions", "Sources"]
DEFAULT_DIR = Path("00-OS/wiki/concepts")
WIKILINK = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")


def parse(path: Path):
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not m:
        return None, None, "no frontmatter"
    try:
        fm = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError as e:
        return None, None, f"bad yaml: {e}"
    body = m.group(2)
    secs = {}
    for name in SECTIONS:
        sm = re.search(rf"^## {re.escape(name)}\s*\n(.*?)(?=^## |\Z)", body, re.S | re.M)
        secs[name] = sm.group(1).strip() if sm else None
    return fm, secs, None


def names_blocklist():
    p = Path("People/_names.md")
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip().lstrip("-*").strip()
        if line and not line.startswith("#") and len(line.split()) <= 4:
            out.append(line.split("|")[0].split("(")[0].strip())
    return [n for n in out if len(n) > 2]


def lint_card(path: Path, names):
    errs = []
    fm, secs, err = parse(path)
    if err:
        return [err]
    if fm.get("type") != "concept-card":
        errs.append("type must be concept-card")
    claim = (fm.get("claim") or "").strip()
    if not claim:
        errs.append("claim empty")
    elif len(re.findall(r"[.!?](\s|$)", claim.rstrip())) > 1:
        errs.append("claim must be one sentence")
    for name in SECTIONS:
        if secs[name] is None:
            errs.append(f"missing section ## {name}")
    if secs["Claim"] is not None and not secs["Claim"]:
        errs.append("## Claim empty")
    mech = secs["Mechanism"] or ""
    if not mech:
        errs.append("## Mechanism empty")
    elif claim and (len(mech) <= len(claim) or claim.rstrip(".").lower() in mech.lower()):
        errs.append("## Mechanism restates the claim — say WHY/HOW")
    edges = fm.get("edges") or []
    if not edges:
        errs.append("edges: need at least one typed edge")
    conn = secs["Connections"] or ""
    for i, e in enumerate(edges):
        if not isinstance(e, dict):
            errs.append(f"edges[{i}] not a mapping"); continue
        t = e.get("type")
        if t not in EDGE_TYPES:
            errs.append(f"edges[{i}] type {t!r} not in {sorted(EDGE_TYPES)}")
        to = str(e.get("to") or "")
        if not WIKILINK.fullmatch(to.strip()):
            errs.append(f"edges[{i}] to must be a [[wikilink]], got {to!r}")
        elif WIKILINK.match(to.strip()).group(1) not in conn:
            errs.append(f"edges[{i}] target {to} not mirrored in ## Connections")
        if not e.get("note"):
            errs.append(f"edges[{i}] needs a note (why)")
        if not e.get("source"):
            errs.append(f"edges[{i}] needs a source slug")
    ev = secs["Evidence"] or ""
    if '"' not in ev and "“" not in ev:
        errs.append("## Evidence needs at least one verbatim quote")
    if not (secs["So what"] or "").strip():
        errs.append("## So what empty — trivia, not a concept")
    if not re.search(r"^\s*-\s+\S", secs["Open questions"] or "", re.M):
        errs.append("## Open questions needs at least one bullet")
    if fm.get("confidence") not in CONFIDENCE:
        errs.append(f"confidence must be one of {sorted(CONFIDENCE)}")
    if fm.get("status") not in STATUS:
        errs.append(f"status must be one of {sorted(STATUS)}")
    full = path.read_text(encoding="utf-8")
    if "People/" in full:
        errs.append("references People/ — firewall")
    for n in names:
        if re.search(rf"\b{re.escape(n)}\b", full):
            errs.append(f"names a person from People/_names.md: {n!r} — use a role")
    return errs


def cards_in(paths):
    for p in paths:
        p = Path(p)
        if p.is_dir():
            yield from sorted(x for x in p.glob("*.md") if not x.name.startswith("_"))
        elif p.suffix == ".md":
            yield p


def cmd_lint(args):
    names = names_blocklist()
    bad = 0
    for card in cards_in(args.paths or [DEFAULT_DIR]):
        errs = lint_card(card, names)
        if errs:
            bad += 1
            print(f"FAIL {card}")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"ok   {card}")
    return 1 if bad else 0


def load_all(d):
    out = {}
    for card in cards_in([d]):
        fm, secs, err = parse(card)
        if not err:
            out[card.stem] = (fm, secs, card)
    return out


def cmd_graph(args):
    for slug, (fm, _, _) in load_all(args.dir).items():
        for e in fm.get("edges") or []:
            if isinstance(e, dict):
                to = WIKILINK.match(str(e.get("to", "")).strip())
                print(f"{slug}\t{e.get('type')}\t{to.group(1) if to else e.get('to')}\t{e.get('source','')}")
    return 0


def cmd_brief_data(args):
    d = Path(args.dir)
    cards = load_all(d)
    today = dt.date.today()
    since = today - dt.timedelta(days=args.since)
    inbound = {s: 0 for s in cards}
    stubs, contested, convergence, fresh, stale_open, one_way = [], [], [], [], [], []
    for slug, (fm, secs, path) in cards.items():
        upd = fm.get("updated") or fm.get("created")
        upd = upd if isinstance(upd, dt.date) else (dt.date.fromisoformat(str(upd)) if upd else None)
        srcs = fm.get("sources") or []
        if upd and upd >= since:
            fresh.append((slug, upd, len(srcs)))
        if len(srcs) >= 3:
            convergence.append((slug, len(srcs), fm.get("confidence")))
        if fm.get("status") == "contested" or any(isinstance(e, dict) and e.get("type") == "contradicts" for e in fm.get("edges") or []):
            contested.append(slug)
        if upd and (today - upd).days >= 30 and re.search(r"^\s*-\s+\S", secs.get("Open questions") or "", re.M):
            stale_open.append((slug, (today - upd).days))
        for e in fm.get("edges") or []:
            if not isinstance(e, dict):
                continue
            m = WIKILINK.match(str(e.get("to", "")).strip())
            if not m:
                continue
            tgt = m.group(1)
            if tgt in cards:
                inbound[tgt] += 1
                back = cards[tgt][0].get("edges") or []
                if not any(isinstance(b, dict) and WIKILINK.match(str(b.get("to", ""))) and WIKILINK.match(str(b.get("to", ""))).group(1) == slug for b in back):
                    one_way.append((slug, e.get("type"), tgt))
            elif not tgt.startswith("t-") and not list(Path("00-OS/wiki").rglob(f"{tgt}.md")):
                stubs.append((slug, tgt))
    orphans = [s for s, n in inbound.items() if n == 0]
    print(f"# brief-data · {today} · window {args.since}d · {len(cards)} cards\n")
    print("## Fresh (new or touched in window)")
    for s, u, n in sorted(fresh, key=lambda x: x[1], reverse=True): print(f"- [[{s}]] · {u} · {n} source(s)")
    print("\n## Convergence candidates (3+ sources)")
    for s, n, c in sorted(convergence, key=lambda x: -x[1]): print(f"- [[{s}]] · {n} sources · confidence {c}")
    print("\n## Contested")
    for s in contested: print(f"- [[{s}]]")
    print("\n## Stale open questions (30d+ untouched)")
    for s, days in sorted(stale_open, key=lambda x: -x[1]): print(f"- [[{s}]] · {days}d")
    print("\n## Stubs (edges to pages that don't exist)")
    for s, t in stubs: print(f"- [[{s}]] → [[{t}]]")
    print("\n## One-way edges (target doesn't link back)")
    for s, t, tgt in one_way: print(f"- [[{s}]] **{t}** → [[{tgt}]]")
    print("\n## Orphans (no inbound edge from another card)")
    for s in orphans: print(f"- [[{s}]]")
    return 0


def cmd_stage(args):
    text = Path(args.file).read_text(encoding="utf-8") if args.file else sys.stdin.read()
    if not text.strip():
        print("nothing to stage", file=sys.stderr); return 1
    out_dir = Path("00-OS/raw/messages"); out_dir.mkdir(parents=True, exist_ok=True)
    today = dt.date.today().isoformat()
    slug = re.sub(r"[^a-z0-9]+", "-", args.slug.lower()).strip("-")
    out = out_dir / f"{today}_{slug}.md"
    fm = {"title": args.slug, "type": "note", "kind": args.kind, "created": today, "source": args.file or "paste",
          "tags": ["raw", "messages", args.kind]}
    out.write_text("---\n" + yaml.safe_dump(fm, sort_keys=False) + "---\n\n" + text.strip() + "\n", encoding="utf-8")
    print(out)
    return 0


def cmd_index(args):
    d = Path(args.dir); cards = load_all(d)
    by_topic = {}
    for slug, (fm, _, _) in cards.items():
        key = str((fm.get("topics") or ["uncategorized"])[0])  # first topic = the lane; the rest are tags
        by_topic.setdefault(key, []).append((slug, str(fm.get("claim") or "").strip().rstrip("."), fm.get("status"), len(fm.get("sources") or [])))
    lines = []
    for key in sorted(by_topic):
        lines.append(f"### {key}")
        for slug, claim, status, n in sorted(by_topic[key]):
            tag = f" · {status}" if status and status != "forming" else ""
            tag += f" · {n} sources" if n > 1 else ""
            lines.append(f"- [[{slug}]] — {claim[0].lower() + claim[1:] if claim else ''}{tag}")
        lines.append("")
    block = "## Cards by topic\n\n" + ("\n".join(lines) if lines else "_None yet._\n") + "\n"
    idx = d / "_index.md"; text = idx.read_text(encoding="utf-8")
    new = re.sub(r"## Cards by topic\n.*?(?=^## |\Z)", lambda m: block, text, count=1, flags=re.S | re.M)
    new = re.sub(r"^updated: .*$", f"updated: {dt.date.today()}", new, count=1, flags=re.M)
    idx.write_text(new, encoding="utf-8")
    print(f"indexed {len(cards)} cards in {len(by_topic)} topic groups -> {idx}")
    return 0


GOOD = """---
title: Test Concept
type: concept-card
domain: concepts
claim: "Doing X reliably produces Y."
source: test-src
sources: [test-src]
edges:
  - {type: causes, to: "[[other-thing]]", note: "seen twice", source: "test-src"}
confidence: low
status: forming
topics: [test]
created: 2026-01-01
updated: 2026-01-01
tags: [concepts, concept-card]
---
# Test Concept
## Claim
Doing X reliably produces Y.
## Mechanism
X removes the bottleneck that was throttling Y, so throughput climbs until the next constraint binds.
## Evidence
- "we did X and Y doubled" — the client · test-src · 2026-01-01
## Connections
- **causes** → [[other-thing]] — seen twice
## Open questions
- Does it hold when Z?
## So what
Do X before buying more capacity.
## Contradictions
_None yet._
## Sources
- [[_sources/test-src]]
"""


def cmd_selftest(_):
    with tempfile.TemporaryDirectory() as td:
        good = Path(td, "good.md"); good.write_text(GOOD)
        assert lint_card(good, []) == [], lint_card(good, [])
        bad = Path(td, "bad.md")
        bad.write_text(GOOD.replace("type: causes", "type: relates").replace("## So what\nDo X before buying more capacity.\n", "## So what\n\n")
                       .replace("X removes the bottleneck that was throttling Y, so throughput climbs until the next constraint binds.", "Doing X reliably produces Y."))
        errs = lint_card(bad, [])
        assert any("not in" in e for e in errs), errs
        assert any("So what" in e for e in errs), errs
        assert any("restates" in e for e in errs), errs
        assert any("names a person" in e for e in lint_card(good, ["client"])), "name blocklist"
    print("selftest ok")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("lint"); p.add_argument("paths", nargs="*"); p.set_defaults(fn=cmd_lint)
    p = sub.add_parser("graph"); p.add_argument("dir", nargs="?", default=DEFAULT_DIR); p.set_defaults(fn=cmd_graph)
    p = sub.add_parser("brief-data"); p.add_argument("dir", nargs="?", default=DEFAULT_DIR); p.add_argument("--since", type=int, default=7); p.set_defaults(fn=cmd_brief_data)
    p = sub.add_parser("stage"); p.add_argument("--kind", required=True, choices=["message", "email", "text", "video", "note", "thread"]); p.add_argument("--slug", required=True); p.add_argument("--file"); p.set_defaults(fn=cmd_stage)
    p = sub.add_parser("index"); p.add_argument("dir", nargs="?", default=DEFAULT_DIR); p.set_defaults(fn=cmd_index)
    p = sub.add_parser("selftest"); p.set_defaults(fn=cmd_selftest)
    a = ap.parse_args()
    sys.exit(a.fn(a))


if __name__ == "__main__":
    main()
