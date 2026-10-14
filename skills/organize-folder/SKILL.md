---
name: organize-folder
description: Organize a messy folder (Desktop by default, or any folder named) into clean category subfolders — LINK-SAFE, with no deletions, a full undo script, and an audit log. Runs a link preflight first and BLOCKS any item an app holds an absolute path into, so tidying never silently blanks a ProPresenter playlist, a Resolve timeline, a Logic session, or a Lightroom catalog. Use on "organize my desktop", "clean up this folder", "sort out my downloads", "/organize-folder", "declutter my desktop", "my downloads/desktop is a mess", "sort my files into folders", "tidy up [folder]", "is it safe to move this folder", or any cluttered directory handed over. NOT for source files inside a code project or repo. Tidies ONE folder into categories.
---

# Organize Folder

Turn a cluttered folder into a small set of clean category subfolders. Works on the Desktop
by default, or any folder the user names. The whole point is **safe and reversible**: nothing
is deleted, project/app folders move intact, and every run leaves its own undo script.

## Hard rules (never break these)

- **Never move a linked item.** Apps store **absolute paths** to files they don't own. Moving
  whole folders intact protects a folder's *insides* and does nothing for the references pointing
  *at* it — the path still changes and every reference still breaks. Run the link preflight
  (step 0) and leave every BLOCKED item exactly where it is.
- **Never move while unaware of links.** If link status can't be determined, this skill downgrades
  to preview-only and says so. There is no "probably fine."
- **Never delete anything.** Only `mv` into category folders.
- **Never overwrite.** On a name collision, the helper auto-suffixes (`name (2)`) into the same
  category so the item still lands and nothing is overwritten; the undo restores the original name.
  If no free name can be found, it's left in place and logged as a CONFLICT.
- **Never reach inside project/app folders.** Move whole folders (editing-app projects, catalogs,
  repos, packages, etc.) as single units — moving their internals breaks references. Organize the
  top level only; never recurse.
- **Leave system/hidden files alone:** every dotfile (`.DS_Store`, `.localized`, `._*`, `.env`, …)
  plus `desktop.ini` and `Thumbs.db` stay put.
- **Categories come from the contents, not a fixed list.** Inventory first, then name folders that
  fit what's actually there. Don't force a generic taxonomy onto a folder that doesn't need it.
- **Default to acting on a small, clear Desktop** (it's reversible — don't stall on confirmation;
  surface judgment calls in the report). **But preview first** when TARGET isn't the Desktop, or
  the run is large/ambiguous (~20+ items, or a non-trivial Archive/`_To Sort` bucket): show the
  plan table and take one quick confirm before running.
- **Re-running is safe.** Each run writes its own timestamped log and undo script, so a second
  organize never overwrites a previous run's undo, and every run stays independently reversible.

## Process

### 0. Link preflight — before anything moves

A folder name is a hint. A link list is proof. `Desktop/PRO 7 2024 MEDIA` on a church media
workstation read a year stale and was the second most-referenced path in every live ProPresenter
playlist — 636 files called by absolute path. Tidying it into `Archive/` blanks slides mid-service.
Editors, DAWs, photo catalogs and sync clients all work the same way.

```bash
GUARD="$HOME/.claude/skills/organize-folder/scripts/link-guard.sh"
[ -x "$GUARD" ] || GUARD="$(git rev-parse --show-toplevel 2>/dev/null || pwd)/Skills/organize-folder/scripts/link-guard.sh"

# (a) A system-audit run exists — pass its saved link list. Cheapest and best.
bash "$GUARD" "<TARGET>" "/tmp/system-audit-<date>/linkindex.tsv" > /tmp/guard.tsv

# (b) No audit — scoped self-check, cached ~24h. Seconds, not the minutes `linkindex` costs.
bash "$GUARD" "<TARGET>" > /tmp/guard.tsv
```

Then feed the verdict to the mover, which enforces it:

```bash
awk -F'\t' '$1=="BLOCKED"{print $2}' /tmp/guard.tsv > /tmp/blocklist.txt
export LINK_BLOCKLIST=/tmp/blocklist.txt
```

**Read the exit status.** `0` = every item got a verdict, proceed (BLOCKED items stay put).
`2` = status undetermined, because macOS TCC denied the app stores. Then `export
LINK_STATUS=unknown`, show the plan, move **nothing**, and tell the user to grant Full Disk Access
to `/bin/bash` and re-run. An unreadable store is not an empty one — that confusion is what made
the scheduled lane report `moved=0` for 28 runs while doing nothing.

`safe-sort.sh` reads both variables and refuses the move itself, so a per-run script can't route
around the gate by forgetting to check. What the guard can and can't see:
`references/link-safety.md`.

### 1. Inventory
List the top level, marking directories. Skip prior-run artifacts and the literal `*` of an empty
folder (portable — this snippet may run under zsh, so no `shopt` here):
```bash
cd "<TARGET>"
for f in *; do
  [ -e "$f" ] || continue                 # empty folder: skip the unmatched '*'
  case "$f" in _ORGANIZE_*|_UNDO_*|_Organize-Undo) continue ;; esac   # leftover artifacts / paper-trail folder
  if [ -d "$f" ]; then echo "DIR  | $f"; else echo "FILE | $f"; fi
done
```
For a large mess, also pull `ls -la` for sizes/dates. If the folder already contains
`_ORGANIZE_*`/`_UNDO_*` artifacts and top-level folders that are clearly category buckets from a
previous organize, leave those buckets in place — don't re-file an already-sorted folder.

### 2. Disambiguate
Peek (one `ls -1 | head` each) into folders whose names don't reveal their purpose before filing
them. A two-second look prevents misfiling a whole folder. Never recurse to re-sort internals.

### 3. Decide categories
Derive the category set from what's actually there, in this order:
1. **Extension clusters → media buckets:** images, video, audio, fonts, docs, sheets, installers/apps.
2. **Name tokens override extension:** `invoice`/`receipt`/`tax`/`contract`/`statement` →
   **Finance & Admin**; `Screenshot `/`Screen Shot `/`Screen Recording ` → **Screenshots**; a
   recurring client/project token → a folder named for it.
3. **Dates:** only feed an `Archive/<year>` bucket on a large, time-structured folder — never on a small one.
4. **No single-item categories:** fold a lone file into the nearest broader bucket. Cap at ~8–16 folders.
5. **One level only:** organize the top level; whole folders move intact.

Routing rules:
- Route only confident items to real categories.
- Drop genuinely ambiguous items into a leading-underscore **`_To Sort`** bucket (exempt from the
  no-singleton rule) and list them in the report under "needs your eye."
- Per-client or per-project material → a folder named for that client/project.
- Old catch-all dumps, `untitled folder*`, stray copies → **Archive**.
- Cross-check your category names against the top-level entries from step 1. If a name already
  exists, pick a distinct bucket; if merging in is intentional, note it as a judgment call. (The
  helper refuses to move into a symlinked category — it logs a SKIP rather than send files outside
  the folder.)

### 4. Generate a per-run sort script
Source the bundled helper by **absolute path**, then emit one `m "<item>" "<Category>"` line per
item. The helper handles mkdir, the dash-safe move, collision auto-suffixing, the undo script, and
the audit log.
Emit an `m` line for every inventoried item, BLOCKED ones included — the helper refuses them and
logs the refusal, which is what puts them in the report. Don't quietly omit them.
```bash
TARGET="$HOME/Desktop"
export LINK_BLOCKLIST=/tmp/blocklist.txt   # from step 0 — the helper refuses these
H="$HOME/.claude/skills/organize-folder/scripts"
[ -d "$H" ] || H="$(git rev-parse --show-toplevel 2>/dev/null || pwd)/Skills/organize-folder/scripts"
source "$H/safe-sort.sh"   # absolute path to THIS skill's helper

m "Some Logo.png"      "Images"
m "Tax Form W9.pdf"    "Finance & Admin"
# ... one m line per inventoried item ...

# Screenshots via glob (modern + pre-Mojave names + recordings):
shopt -s nullglob
for f in Screenshot\ *.png "Screen Shot "*.png "Screen Recording "*.mov; do m "$f" "Screenshots"; done
shopt -u nullglob

sort_summary
```
Write the per-run script to a **scratch path** (e.g. a temp dir), not into TARGET. Run it with
**bash explicitly** — `bash /tmp/run-sort.sh`, never `sh` or the bare path. The per-run script and
the helper use bash-only features (`printf %q` for the undo, `shopt -s nullglob`); under zsh
`shopt` errors and `%q` quoting diverges, which can corrupt the reversible undo. macOS system
`/bin/bash` (3.2) is sufficient — no newer bash needed.

### 4.5 Preview the plan (no run needed)
The per-run script is just a flat list of `m "<item>" "<Category>"` lines, so render the plan
straight from that source — folder | items it will receive | count — **without executing anything**.
This costs nothing and lets the user catch a misroute before any file moves.
- Small/clear Desktop: showing the plan is optional; act-first is fine.
- Non-Desktop target, or a large/ambiguous run: show the plan table and wait for one quick confirm,
  then run.

Editing a route is just editing an `m` line — no separate preview mode to maintain, and the real
run stays fully reversible via its undo script.

### 5. Run, verify, report
After running, re-list the top level and show the result as a table (folder | item count | what's
in it). The helper prints `LOG=…` and `UNDO=…` for this run — cite those **exact printed paths**
(don't assume the names), then give the user:
- the **undo command**: `bash "<UNDO path the helper printed>"` (run it with bash),
- the **audit log**: `<LOG path the helper printed>`,
- an optional **reveal in Finder**: offer the command `open "<TARGET>"` as copy-paste text —
  don't auto-run it (a headless/automated session shouldn't pop a Finder window),
- a short list of **judgment calls** to override: items parked in `_To Sort`, best-guess routes,
  and any collision renames (the `RENAMED` lines in the log).

Then, whenever the guard blocked anything, a section under this exact heading — table filled
straight from `/tmp/guard.tsv` (item, `APPS`, `REFS`):

```markdown
## DO NOT MOVE — linked

Left exactly where they were. An app holds an absolute path into each; moving it without
updating that path breaks it.

| Item | Referencing app | References |
|---|---|---|
| `PRO 7 2024 MEDIA` | ProPresenter | 636 |

To move one: re-link it inside the app (ProPresenter → media browser → relocate), re-run the
audit so the old path drops off the link list, then re-run organize-folder. It moves on the
second pass because it is genuinely no longer referenced.
```

A block is the skill working, not a failure — and not permanent. Re-link-then-re-run is the normal
two-step; a repoint layer that rewrites the reference so it follows the file is the intended
follow-on.

## What the helper produces (`~/_Organize-Undo/`, one timestamped set per run)
Logs and undo scripts do **not** land in the folder being tidied. Every Desktop / Downloads /
Documents / other run writes into `~/_Organize-Undo/` (override with `ORGANIZE_ARTIFACT_DIR`):
- `_ORGANIZE_LOG_<Folder>_<stamp>.txt` — every move, plus BLOCKED / RENAMED / CONFLICT / SKIP /
  FAILED / BAD-CALL lines. Header is `TARGET=` + `STAMP=`. Summary carries `blocked=` alongside
  `moved=` and `skipped=`.
- `_UNDO_ORGANIZE_<Folder>_<stamp>.sh` — run it to put that run's moves back exactly; it's
  no-clobber and idempotent, cds to TARGET, and on undo also removes the empty buckets the run
  created. A second organize never overwrites a previous run's undo.

## Notes
- For folders other than the Desktop, set `TARGET=<path>` before sourcing the helper, and show the
  plan before running.
- Run the per-run script and the undo script with **bash**, not sh/zsh — they rely on bash
  `printf %q` and `shopt nullglob`. macOS `/bin/bash` 3.2 is fine.
- High-blast-radius targets (`/`, your home folder, `/Users`, `/System`, `/Library`) are refused by
  default — organizing them would scoop OS/app folders into ad-hoc buckets and isn't cleanly
  reversible. Prefix `FORCE=1` (e.g. `FORCE=1 bash run.sh`) only if you truly mean it.
- The helper lives next to this file at `scripts/safe-sort.sh`; the link preflight at
  `scripts/link-guard.sh`. Both are bash 3.2-safe.

