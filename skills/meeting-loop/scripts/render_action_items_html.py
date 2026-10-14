#!/usr/bin/env python3
"""
render_action_items_html.py — turn a small action-items JSON into a self-contained,
single-file HTML view with JSON + Markdown export buttons.

Usage:
    python render_action_items_html.py INPUT.json OUTPUT.html

Design goals:
- SMALL, self-contained file. No external fonts, no CDN, no network calls.
- "Export JSON" and "Export MD" buttons that download the CURRENT state (checkboxes included),
  so the person can send either back.
- Task sections render as checkable to-dos; note sections render as titled blurbs.
- Checkbox state persists locally (localStorage) so reopening keeps progress.
- Optional brand styling: set "brand": "<slug>" in the JSON to apply that brand's
  palette + fonts (embedded base64 so the file stays portable and on-brand anywhere).

JSON schema (title + sections required; everything else optional):
{
  "title": "...", "subtitle": "...", "date": "YYYY-MM-DD", "person": "...", "meeting": "...",
  "brand": "<slug>",                          # optional — applies brand kit
  "eyebrow": "TEAM NAME",                     # optional label above the title
  "accent": "#1A1714",                        # optional; brand overrides
  "sections": [
    { "id": "...", "heading": "...", "kind": "tasks", "note": "...",
      "items": [ {"task": "...", "detail": "..."} ] },
    { "id": "...", "heading": "...", "kind": "notes",
      "items": [ {"title": "...", "body": "..."} ] }
  ]
}
"""
import base64
import json
import os
import sys
from html import escape
from pathlib import Path




def brand_kit(name):
    """Return (fontface_css, root_vars_css) for a named brand, or generic defaults."""
    # generic warm default
    root = """:root{
    --accent:#E8A33D; --accent-dark:#c9862a;
    --ink:#23201c; --muted:#6f675d;
    --paper:#fbf7f1; --card:#ffffff; --line:#e9e1d6; --panel:#f6f0e8;
    --font-head:Georgia, "Times New Roman", serif;
    --font-body:-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    --font-label:-apple-system, "Segoe UI", Roboto, sans-serif;
  }"""
    return "", root


TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
__FONTFACE__
__ROOT__
  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--paper); color: var(--ink);
    font: 16px/1.6 var(--font-body); -webkit-font-smoothing: antialiased;
  }
  .wrap { max-width: 760px; margin: 0 auto; padding: 40px 24px 90px; }
  .eyebrow { font-family: var(--font-label); text-transform: uppercase; letter-spacing: .16em;
             font-size: 11px; color: var(--accent); margin: 0 0 10px; }
  header { display: flex; align-items: flex-start; justify-content: space-between; gap: 18px;
           border-bottom: 1px solid var(--line); padding-bottom: 20px; margin-bottom: 8px; }
  h1 { font-family: var(--font-head); font-weight: 400; font-size: 31px; line-height: 1.1;
       margin: 0 0 8px; letter-spacing: -0.01em; }
  .sub { color: var(--muted); font-size: 15px; max-width: 46ch; }
  .meta { font-family: var(--font-label); text-transform: uppercase; letter-spacing: .1em;
          color: var(--muted); font-size: 11px; margin-top: 10px; }
  .toolbar { display: flex; gap: 8px; flex: 0 0 auto; }
  .btn { cursor: pointer; font-family: var(--font-label); text-transform: uppercase;
         letter-spacing: .08em; font-size: 11px; padding: 10px 13px; border-radius: 2px;
         border: 1px solid var(--accent); background: var(--accent); color: var(--paper); white-space: nowrap; }
  .btn:hover { background: var(--accent-dark); border-color: var(--accent-dark); }
  .btn.ghost { background: transparent; color: var(--ink); border-color: var(--line); }
  .btn.ghost:hover { border-color: var(--ink); background: transparent; }
  section { margin-top: 36px; }
  h2 { font-family: var(--font-head); font-weight: 400; font-size: 21px; margin: 0 0 6px;
       display: flex; align-items: baseline; gap: 12px; letter-spacing: -0.01em; }
  h2 .count { font-family: var(--font-label); text-transform: uppercase; letter-spacing: .1em;
              font-size: 10px; color: var(--muted); font-weight: normal; }
  .sec-note { color: var(--muted); font-size: 14px; font-style: italic; margin: 0 0 14px; max-width: 60ch; }
  ul { list-style: none; margin: 0; padding: 0; }
  li.task { background: var(--card); border: 1px solid var(--line); border-radius: 3px;
            padding: 13px 15px; margin-bottom: 8px; display: flex; gap: 13px; align-items: flex-start; }
  li.task input { margin-top: 3px; width: 17px; height: 17px; accent-color: var(--accent); flex: 0 0 auto; cursor: pointer; }
  li.task .body { flex: 1; }
  li.task .t { line-height: 1.4; }
  li.task.done .t { text-decoration: line-through; color: var(--muted); }
  li.task .d { color: var(--muted); font-size: 14px; margin-top: 3px; line-height: 1.5; }
  li.note { background: var(--panel); border: 1px solid var(--line); border-left: 2px solid var(--accent);
            border-radius: 3px; padding: 15px 17px; margin-bottom: 8px; }
  li.note .t { font-family: var(--font-head); color: var(--accent); font-size: 17px; margin-bottom: 4px; }
  li.note .d { color: var(--ink); font-size: 15px; line-height: 1.6; }
  footer { margin-top: 50px; color: var(--muted); font-size: 11px; font-family: var(--font-label);
           text-transform: uppercase; letter-spacing: .08em; border-top: 1px solid var(--line); padding-top: 16px; }
  .toast { position: fixed; bottom: 22px; left: 50%; transform: translateX(-50%);
           background: var(--ink); color: var(--paper); padding: 11px 17px; border-radius: 3px;
           font-size: 13px; font-family: var(--font-label); text-transform: uppercase; letter-spacing: .06em;
           opacity: 0; transition: opacity .2s; pointer-events: none; }
  .toast.show { opacity: 1; }
  @media (max-width: 560px) { header { flex-direction: column; } h1 { font-size: 26px; } }
  @media print { .toolbar { display: none; } body { background: #fff; } li.task, li.note { break-inside: avoid; } }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div>
      <div class="eyebrow" id="h-eyebrow"></div>
      <h1 id="h-title"></h1>
      <div class="sub" id="h-sub"></div>
      <div class="meta" id="h-meta"></div>
    </div>
    <div class="toolbar">
      <button class="btn ghost" onclick="resetChecks()">Reset</button>
      <button class="btn ghost" onclick="exportMD()">Export MD</button>
      <button class="btn" onclick="exportJSON()">Export JSON</button>
    </div>
  </header>
  <main id="content"></main>
  <footer id="foot"></footer>
</div>
<div class="toast" id="toast"></div>
<script>
const DATA = __DATA__;
const KEY = "aiv:" + (DATA.person || "") + ":" + (DATA.date || "") + ":" + (DATA.title || "");

function loadState() { try { return JSON.parse(localStorage.getItem(KEY)) || {}; } catch (e) { return {}; } }
function saveState(s) { try { localStorage.setItem(KEY, JSON.stringify(s)); } catch (e) {} }
let state = loadState();

function render() {
  const eb = document.getElementById("h-eyebrow");
  if (DATA.eyebrow) { eb.textContent = DATA.eyebrow; } else { eb.style.display = "none"; }
  document.getElementById("h-title").textContent = DATA.title || "Action Items";
  document.getElementById("h-sub").textContent = DATA.subtitle || "";
  const meta = [DATA.person, DATA.meeting, DATA.date].filter(Boolean).join("  ·  ");
  document.getElementById("h-meta").textContent = meta;
  document.title = DATA.title || "Action Items";

  const root = document.getElementById("content");
  root.innerHTML = "";
  (DATA.sections || []).forEach((sec, si) => {
    const s = document.createElement("section");
    const h = document.createElement("h2");
    h.textContent = sec.heading || "";
    if (sec.kind === "tasks") {
      const c = document.createElement("span");
      c.className = "count";
      c.textContent = (sec.items || []).length + " to do";
      h.appendChild(c);
    }
    s.appendChild(h);
    if (sec.note) { const p = document.createElement("p"); p.className = "sec-note"; p.textContent = sec.note; s.appendChild(p); }
    const ul = document.createElement("ul");
    (sec.items || []).forEach((it, ii) => {
      const key = si + "-" + ii;
      const li = document.createElement("li");
      if (sec.kind === "tasks") {
        li.className = "task" + (state[key] ? " done" : "");
        const cb = document.createElement("input");
        cb.type = "checkbox"; cb.checked = !!state[key];
        cb.onchange = () => { state[key] = cb.checked; saveState(state); li.classList.toggle("done", cb.checked); };
        const body = document.createElement("div"); body.className = "body";
        const t = document.createElement("div"); t.className = "t"; t.textContent = it.task || it.title || "";
        body.appendChild(t);
        if (it.detail || it.body) { const d = document.createElement("div"); d.className = "d"; d.textContent = it.detail || it.body; body.appendChild(d); }
        li.appendChild(cb); li.appendChild(body);
      } else {
        li.className = "note";
        const t = document.createElement("div"); t.className = "t"; t.textContent = it.title || "";
        const d = document.createElement("div"); d.className = "d"; d.textContent = it.body || it.detail || "";
        li.appendChild(t); li.appendChild(d);
      }
      ul.appendChild(li);
    });
    s.appendChild(ul);
    root.appendChild(s);
  });
  document.getElementById("foot").textContent =
    "Private planning view" + (DATA.date ? "  ·  " + DATA.date : "") + "  ·  generated by meeting-loop  ·  checkbox progress saved on this device only";
}

function currentExport() {
  const out = JSON.parse(JSON.stringify(DATA));
  (out.sections || []).forEach((sec, si) => {
    if (sec.kind !== "tasks") return;
    (sec.items || []).forEach((it, ii) => { it.done = !!state[si + "-" + ii]; });
  });
  out.exported_at = new Date().toISOString();
  return out;
}

function buildMD() {
  const L = [];
  if (DATA.eyebrow) L.push("<!-- " + DATA.eyebrow + " -->");
  L.push("# " + (DATA.title || "Action Items"));
  const meta = [DATA.subtitle, DATA.person, DATA.date].filter(Boolean).join("  ·  ");
  if (meta) L.push("*" + meta + "*");
  L.push("");
  (DATA.sections || []).forEach((sec, si) => {
    L.push("## " + (sec.heading || ""));
    if (sec.note) { L.push("*" + sec.note + "*"); L.push(""); }
    (sec.items || []).forEach((it, ii) => {
      if (sec.kind === "tasks") {
        const box = state[si + "-" + ii] ? "x" : " ";
        const d = (it.detail || it.body) ? " — " + (it.detail || it.body) : "";
        L.push("- [" + box + "] " + (it.task || it.title || "") + d);
      } else {
        L.push("**" + (it.title || "") + "**");
        if (it.body || it.detail) L.push(it.body || it.detail);
        L.push("");
      }
    });
    L.push("");
  });
  return L.join("\\n").replace(/\\n{3,}/g, "\\n\\n").trim() + "\\n";
}

function download(text, ext, mime) {
  const blob = new Blob([text], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  const base = ((DATA.person || "action-items") + "-" + (DATA.date || "")).replace(/[^a-z0-9\\-]+/gi, "-").toLowerCase();
  a.href = url; a.download = base + "." + ext;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  toast("Exported " + a.download);
}

function exportJSON() { download(JSON.stringify(currentExport(), null, 2), "json", "application/json"); }
function exportMD() { download(buildMD(), "md", "text/markdown"); }
function resetChecks() { state = {}; saveState(state); render(); toast("Checkboxes reset"); }

let tmr;
function toast(msg) {
  const el = document.getElementById("toast");
  el.textContent = msg; el.classList.add("show");
  clearTimeout(tmr); tmr = setTimeout(() => el.classList.remove("show"), 1800);
}

render();
</script>
</body>
</html>
"""


def render_html(data):
    """Action-items payload (schema above) -> self-contained HTML string."""
    fontface, root = brand_kit(data.get("brand"))
    if data.get("accent"):  # only the generic palette carries #E8A33D, so a brand kit's accent wins
        root = root.replace("--accent:#E8A33D;", f"--accent:{data['accent']};")
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return (TEMPLATE
            .replace("__TITLE__", escape(str(data.get("title", "Action Items"))))
            .replace("__FONTFACE__", fontface)
            .replace("__ROOT__", root)
            .replace("__DATA__", payload))


def main():
    if len(sys.argv) != 3:
        print("usage: render_action_items_html.py INPUT.json OUTPUT.html", file=sys.stderr)
        sys.exit(2)
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    dst.write_text(render_html(json.loads(src.read_text())))
    print(str(dst))


if __name__ == "__main__":
    main()
