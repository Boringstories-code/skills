#!/bin/bash
# safe-sort.sh — reusable, reversible folder-sorting helper.
#
# Usage from a per-run script (run it with BASH, not sh/zsh):
#   TARGET="$HOME/Desktop"        # folder being organized (default: ~/Desktop)
#   source /abs/path/to/safe-sort.sh   # sets up timestamped log + undo, defines m() and sort_summary()
#   m "Some File.pdf" "Finance & Admin"
#   m "Project Folder"  "Clients"
#   sort_summary
#
# Guarantees:
#   - NOTHING is deleted. Only mv into category folders.
#   - Never overwrites. On a name collision the item is auto-suffixed "name (n)" into the
#     same category; only if no free name is found is it left in place and logged as CONFLICT.
#   - Whole folders move intact (never reaches inside app/project folders).
#   - Every move is gated on the real mv exit status, so the log/undo never record a move
#     that didn't happen.
#   - LINK-SAFE: if LINK_BLOCKLIST names a file (one item name per line, produced by
#     link-guard.sh), every item in it is refused — an app holds an absolute path into it
#     and moving it would silently break that reference. Set LINK_STATUS=unknown when link
#     status could not be determined; the helper then refuses EVERY move (preview-only).
#   - Writes a timestamped _ORGANIZE_LOG_<Folder>_<stamp>.txt (audit) and an idempotent
#     _UNDO_ORGANIZE_<Folder>_<stamp>.sh (full reversal) into ~/_Organize-Undo (override with
#     ORGANIZE_ARTIFACT_DIR). Re-running never clobbers a prior run's undo — each run is
#     independently reversible. The undo cds to TARGET (quoted), not to its own folder.

set -u
TARGET="${TARGET:-$HOME/Desktop}"

# Refuse catastrophic / not-cleanly-reversible targets (FORCE=1 overrides). Resolve first so a
# relative path or trailing slash can't slip past. The firmlink-backed user home (real files at
# /System/Volumes/Data/Users/...) is explicitly allowed so the Desktop/Downloads case works.
_t="$(cd "$TARGET" 2>/dev/null && pwd -P)"; [ -n "$_t" ] || _t="$TARGET"
case "$_t" in
  /System/Volumes/Data/Users/*) : ;;
  "/"|"$HOME"|"/Users"|/System|/System/*|/Library|/Library/*)
    [ "${FORCE:-0}" = 1 ] || { echo "Refusing to organize $_t without FORCE=1 (set FORCE=1 to override)"; exit 1; } ;;
esac
unset _t

cd "$TARGET" || { echo "cannot cd to $TARGET"; exit 1; }
TARGET="$PWD"   # canonicalize to absolute so the undo's cd never resolves relative to cwd

# Paper trail lives outside the folder being tidied, so Desktop/Downloads/Documents stay
# clean. Override with ORGANIZE_ARTIFACT_DIR (absolute) if a test or a different home wants it.
ARTIFACT_DIR="${ORGANIZE_ARTIFACT_DIR:-$HOME/_Organize-Undo}"
mkdir -p -- "$ARTIFACT_DIR" || { echo "cannot create $ARTIFACT_DIR"; exit 1; }
if [ ! -f "$ARTIFACT_DIR/README.txt" ]; then
  cat > "$ARTIFACT_DIR/README.txt" <<'RM'
These files are the paper trail for folder cleanups (Desktop, Downloads, Documents, anywhere else).

_ORGANIZE_LOG_<Folder>_<stamp>.txt   — what moved, what was left, why
_UNDO_ORGANIZE_<Folder>_<stamp>.sh   — run with bash to put that run back

Nothing here deletes files. Each undo is no-clobber and only reverses its own run.
RM
fi
_art_name="${ARTIFACT_DIR##*/}"
_label="${TARGET##*/}"
[ -n "$_label" ] || _label="folder"

STAMP="$(date +%Y%m%d-%H%M%S)-$$"   # PID makes the stamp unique per run process
LOG="$ARTIFACT_DIR/_ORGANIZE_LOG_${_label}_$STAMP.txt"
UNDO="$ARTIFACT_DIR/_UNDO_ORGANIZE_${_label}_$STAMP.sh"
# Belt-and-suspenders: never reuse a log/undo name (even within the same second or same process),
# so a second run can never truncate/regenerate a prior run's log or undo. Each run stays reversible.
_seq=1
while [ -e "$LOG" ] || [ -e "$UNDO" ]; do
  _seq=$((_seq+1))
  LOG="$ARTIFACT_DIR/_ORGANIZE_LOG_${_label}_$STAMP-$_seq.txt"
  UNDO="$ARTIFACT_DIR/_UNDO_ORGANIZE_${_label}_$STAMP-$_seq.sh"
done
{
  echo "TARGET=$TARGET"
  echo "STAMP=$STAMP"
} > "$LOG"
# Generate the undo script. TARGET is baked in via printf %q (not interpolated into an
# unquoted line). restore() is no-clobber + idempotent: it skips a vanished source and
# refuses an occupied destination.
{
  echo '#!/bin/bash'
  echo '# Undo this organization. Run:  bash "<thisfile>"'
  echo 'set -u'
  printf 'cd %q || { echo "UNDO: cannot cd to organized folder"; exit 1; }\n' "$TARGET"
  echo 'restore(){ { [ -e "$1" ] || [ -L "$1" ]; } || { echo "UNDO-SKIP missing: $1"; return; }; { [ -e "$2" ] || [ -L "$2" ]; } && { echo "UNDO-SKIP occupied: $2"; return; }; mv -- "$1" "$2"; }'
} > "$UNDO"
chmod +x "$UNDO"

_moved=0; _skipped=0; _blocked=0
_created_cats=()

# --- LINK SAFETY -------------------------------------------------------------
# Apps store ABSOLUTE paths to files they don't own. Moving whole folders intact
# protects a folder's insides and does nothing for the references pointing AT it —
# the path still changes, and every reference still breaks. link-guard.sh works out
# which top-level items are referenced; this is where that verdict is enforced, so a
# hand-written per-run script can't route around it by forgetting to check.
LINK_BLOCKLIST="${LINK_BLOCKLIST:-}"
LINK_STATUS="${LINK_STATUS:-}"
if [ -n "$LINK_BLOCKLIST" ] && [ ! -f "$LINK_BLOCKLIST" ]; then
  echo "LINK_BLOCKLIST points at a missing file: $LINK_BLOCKLIST — refusing to move link-blind"; exit 1
fi
if [ "$LINK_STATUS" = "unknown" ]; then
  echo "LINK_STATUS=unknown — link status could not be determined. Preview only; no moves." | tee -a "$LOG"
fi

# Exact-line membership test. No regex, no globbing: item names contain [](). etc.
_is_blocked(){
  [ -n "$LINK_BLOCKLIST" ] || return 1
  grep -qxF -- "$1" "$LINK_BLOCKLIST" 2>/dev/null
}

# m <source> <category-folder>
m(){
  # Arity guard: a malformed generated line (missing/empty category) must not abort the whole
  # sourced run under set -u, and an empty category must never mv an item into "/".
  if [ "$#" -lt 2 ] || [ -z "${2:-}" ]; then
    echo "BAD-CALL (need src + category): ${1:-?}" >> "$LOG"; _skipped=$((_skipped+1)); return
  fi
  local src="${1%/}" cat="$2" base dest stem ext n

  # Skip our own artifacts, the paper-trail folder, Windows turds, and ALL dotfiles.
  case "$src" in
    _ORGANIZE_LOG_*.txt|_UNDO_ORGANIZE_*.sh|desktop.ini|Thumbs.db|.*)
      echo "SKIP (system/self/hidden): $src" >> "$LOG"; _skipped=$((_skipped+1)); return ;;
  esac
  if [ -n "${_art_name:-}" ] && [ "$src" = "$_art_name" ]; then
    echo "SKIP (system/self/hidden): $src" >> "$LOG"; _skipped=$((_skipped+1)); return
  fi

  # Link gate — before anything else that could move a file.
  if [ "$LINK_STATUS" = "unknown" ]; then
    echo "BLOCKED (link status unknown — preview only): $src" >> "$LOG"; _blocked=$((_blocked+1)); return
  fi
  if _is_blocked "$src"; then
    echo "BLOCKED (linked — an app holds an absolute path into this): $src" >> "$LOG"
    _blocked=$((_blocked+1)); return
  fi

  # Never move a category folder into itself (e.g. re-run: m "Images" "Images").
  if [ "$src" = "$cat" ]; then
    echo "SKIP (src == category): $src" >> "$LOG"; _skipped=$((_skipped+1)); return
  fi

  if [ -e "$src" ] || [ -L "$src" ]; then
    # Refuse a symlinked category — moving into it would send files OUTSIDE the folder.
    if [ -L "$cat" ]; then
      echo "SKIP (category is a symlink): $cat" >> "$LOG"; _skipped=$((_skipped+1)); return
    fi
    # Create the category only if it doesn't already exist, and remember it so undo can rmdir
    # the (empty) buckets THIS run created — never a folder the user already had.
    if [ ! -d "$cat" ]; then
      if mkdir -p -- "$cat"; then _created_cats+=("$cat")
      else echo "FAILED (mkdir): $cat" >> "$LOG"; _skipped=$((_skipped+1)); return; fi
    fi

    base="${src##*/}"   # dash-safe, subprocess-free basename (BSD basename errors on leading '-')
    dest="$base"

    # On collision (or a dangling symlink at the destination), find a free "name (n)" in the
    # SAME category so the item still lands — never overwrite.
    if [ -e "$cat/$dest" ] || [ -L "$cat/$dest" ]; then
      if [ -d "$src" ]; then
        stem="$base"; ext=""                       # never split a folder name on a dot
      else
        case "$base" in
          ?*.*) ext="${base##*.}"
                case "$ext" in
                  ""|*" "*) stem="$base"; ext="" ;;          # tail isn't a real extension
                  *)        stem="${base%.*}"; ext=".$ext" ;;
                esac ;;
          *)    stem="$base"; ext="" ;;                      # no extension
        esac
      fi
      n=1
      while { [ -e "$cat/$dest" ] || [ -L "$cat/$dest" ]; } && [ "$n" -lt 999 ]; do
        n=$((n+1)); dest="$stem ($n)$ext"
      done
      if [ -e "$cat/$dest" ] || [ -L "$cat/$dest" ]; then
        echo "CONFLICT (left in place): $src — no free name in $cat after 999 tries" >> "$LOG"
        _skipped=$((_skipped+1)); return
      fi
    fi

    # Gate the undo line, log, and counter on the ACTUAL mv result.
    if mv -- "$src" "$cat/$dest"; then
      printf 'restore %q %q\n' "$cat/$dest" "$src" >> "$UNDO"
      if [ "$dest" = "$base" ]; then
        echo "MOVED: $src  ->  $cat/" >> "$LOG"
      else
        echo "RENAMED (collision): $src  ->  $cat/$dest" >> "$LOG"
      fi
      _moved=$((_moved+1))
    else
      echo "FAILED (left in place): $src  ->  $cat/$dest" >> "$LOG"; _skipped=$((_skipped+1))
    fi
  else
    echo "SKIP (missing): $src" >> "$LOG"; _skipped=$((_skipped+1))
  fi
}

sort_summary(){
  # Append rmdir lines for the empty buckets this run created (after the restore lines, so items
  # are put back first). Quoted + guarded for bash 3.2 + set -u on an empty array.
  if [ "${#_created_cats[@]}" -gt 0 ]; then
    local c
    for c in "${_created_cats[@]}"; do
      # Remove the created bucket AND any empty ancestors it introduced (e.g. Archive/2024 -> also
      # Archive if now empty), walking up but never touching TARGET itself. Stops at the first
      # non-empty dir, so a pre-existing or still-populated parent is left alone.
      printf 'd=%q; while [ "$d" != "." ] && [ "$d" != "/" ]; do rmdir -- "$d" 2>/dev/null || break; d=$(dirname "$d"); done\n' "$c" >> "$UNDO"
    done
  fi
  echo "" >> "$LOG"
  echo "SUMMARY: moved=$_moved skipped=$_skipped blocked=$_blocked" >> "$LOG"
  echo "moved=$_moved skipped=$_skipped blocked=$_blocked"
  echo "LOG=$LOG"
  echo "UNDO=$UNDO"
  if [ "$_blocked" -gt 0 ]; then
    echo "BLOCKED=$_blocked  (linked items left in place — see the BLOCKED lines in the log)"
  fi
}
