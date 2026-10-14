# Link safety — how the preflight decides

Read this when a verdict surprises you, when you need to explain a BLOCK to a user, or when you're
deciding whether to trust a CLEAR.

## The problem in one paragraph

Applications store **absolute paths** to files they don't own. ProPresenter doesn't copy a clip
into its library when you drag it onto a slide; it writes `/Users/x/Desktop/PRO 7 2024
MEDIA/clip.mov` into the playlist. So does Resolve, Premiere, Logic, Ableton, Lightroom, After
Effects, Companion, and most launchers and sync clients. `organize-folder`'s existing rule — move
whole folders intact, never recurse — protects the folder's *internal* structure and does nothing
for those references. The folder's own path changes, and every reference into it dies. That is the
seam `link-guard.sh` closes.

## Two modes

**Mode A — a manifest was handed in.** The natural handoff from a `system-audit` run. The expensive
sweep already happened; the guard just reads the file. Accepted shapes, mixed freely:

```
/abs/path
[OK]<TAB>/abs/path                 # scan.sh extract-paths, scan.sh appreach
APP<TAB>[OK]<TAB>/abs/path         # scan.sh linkindex  ← best: carries the app name
```

Prefer a `linkindex`-shaped manifest. The others work, but with no app column the report can only
say "something references this," which is a much weaker sentence to hand a user.

**Mode B — no manifest, so run a scoped self-check.** Never assume clear. The guard sweeps the
places macOS apps actually keep references (`~/Library/Application Support`, `Containers`, `Group
Containers`, `Preferences`, `Saved Application State`) and asks only one question: does anything in
there mention a path under TARGET?

Why this instead of `scan.sh linkindex`: `linkindex` `strings`-extracts *every* external path on
the machine — minutes of work and tens of thousands of lines, almost none of it about this folder.
The guard inverts the cost:

1. one cheap fixed-string `grep -l` pass for the TARGET prefix and its percent-encoded twin;
2. `strings` only the handful of files that matched;
3. keep only decoded paths that actually sit under TARGET.

Same guarantee as `linkindex` *for this folder*, a fraction of the cost. Results cache per-target
for 24h (`~/Library/Caches/link-guard/`), so a preview and the real run don't pay twice.
`LINK_GUARD_REFRESH=1` re-sweeps; `LINK_GUARD_TTL` changes the window; `LINK_GUARD_STORES`
(colon-separated) scopes the sweep to one suspect app.

## What it can and can't see

**Can't miss:** a live reference stored as literal text in an app's own data store. That covers
binary plists, SQLite, and zipped XML, because nearly every format writes the path as text
somewhere inside. This is the property that matters.

**Can miss:** a reference stored only in a project file that lives *outside* the swept stores —
a `.prproj` sitting on an external drive, say. If the user names a project file, crack it directly
with `scan.sh extract-paths` and pass the result as a manifest.

**Can miss:** a reference held only in RAM by a running app. Cheap cross-check when it matters:
`scan.sh openfiles`.

**Can over-report:** a path fragment pulled out of prose in a notes file reads as a reference. That
produces a false BLOCK, which costs one folder staying tidy. Compare with a false CLEAR, which
costs a blank slide during a service. The guard biases every ambiguous call toward BLOCKED, on
purpose.

## The salvage rule

Real paths contain spaces, so the extraction regex has to allow them — which means it also swallows
whatever byte junk followed the path inside the blob. `PRO 7 2024 MEDIA` arrives as `PRO 7 2024
MEDIA \x1bpv`. The guard trims trailing space-delimited tokens (up to 8) until the name resolves
against a real entry in TARGET. A genuinely spaced name resolves on the untrimmed pass and never
enters the loop. Without this, junk silently turns a BLOCKED item into a CLEAR one — the one error
direction that loses data. `scan.sh`'s `report_path()` does the same thing for the same reason.

## Exit 2 is not "clear"

Zero readable files across every app store means macOS TCC denied access, not that no app links
anything. This is the same failure that made the scheduled organize job report a cheerful `moved=0`
for 28 consecutive runs while organizing nothing. The guard exits 2, the skill sets
`LINK_STATUS=unknown`, and `safe-sort.sh` refuses every move. Fix: grant Full Disk Access to
`/bin/bash` (System Settings → Privacy & Security → Full Disk Access → `+` → Cmd-Shift-G →
`/bin/bash`), then re-run.

## Enforcement lives in the mover

The blocklist is enforced inside `safe-sort.sh`'s `m()`, not in the per-run script that calls it.
A generated sort script that forgets to check, or an unattended lane that skips the preflight,
still can't move a blocked item. `LINK_STATUS=unknown` blocks everything by the same mechanism.

## Getting a blocked item moved

Blocked is a state, not a verdict on the file. Two legitimate routes:

1. **Re-link in the app**, then re-run the audit. Once the app points somewhere else, the old path
   drops off the link list and the item passes on the next run.
2. **Repoint the reference** so it follows the file. That's the intended follow-on layer to this
   system — neither this skill nor `system-cleanup` rewrites app data, which is exactly why they
   stop rather than move.
