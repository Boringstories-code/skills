#!/bin/bash
#
# link-guard.sh — answer one question before organize-folder moves anything:
#
#     "Does any application hold an absolute path into this item?"
#
# Apps store absolute paths to files they do not own (ProPresenter, Resolve, Logic,
# Lightroom, Premiere, launchers, sync clients). Moving a linked folder changes its
# absolute path and silently blanks every reference into it. organize-folder moves
# whole folders intact — which protects the folder's INTERNAL structure and does
# nothing at all for the references pointing AT it. This script closes that seam.
#
# READ-ONLY. It never moves, deletes, or writes anything except its own cache.
#
# Usage:
#   link-guard.sh <TARGET-DIR> [LINK-MANIFEST]
#
#   LINK-MANIFEST (optional) — a saved link list from a system-audit run. Accepted
#   shapes, mixed freely, one reference per line:
#       /abs/path
#       [OK]<TAB>/abs/path                       (scan.sh extract-paths / appreach)
#       APP<TAB>[OK]<TAB>/abs/path               (scan.sh linkindex)
#   Anything else on the line is ignored.
#
#   With no manifest it runs a SCOPED SELF-CHECK instead of assuming the folder is
#   clear — see "Mode B" below. It never proceeds link-blind and never reports CLEAR
#   for something it did not actually check.
#
# Output — TSV on stdout, one line per top-level item, then an @-prefixed summary:
#   STATUS	ITEM	REFS	APPS
#   BLOCKED	PRO 7 2024 MEDIA	636	ProPresenter
#   CLEAR	logo.png	0	-
#   UNKNOWN	Some Folder	0	(link status undetermined)
#   @MODE	manifest|selfcheck|cache
#   @SOURCE	<where the reference data came from>
#   @BLOCKED / @CLEAR / @UNKNOWN	<counts>
#
# Exit status:
#   0  link status determined for every item (BLOCKED and CLEAR are both a result)
#   2  link status COULD NOT be determined — caller MUST downgrade to preview-only
#   1  usage / argument error
#
# Env:
#   LINK_GUARD_TTL=86400     cache lifetime in seconds for a Mode B sweep
#   LINK_GUARD_REFRESH=1     ignore the cache, re-sweep
#   LINK_GUARD_CACHE_DIR     default ~/Library/Caches/link-guard
#   LINK_GUARD_STORES        override the app stores swept (colon/newline separated)
#
# -e -u but deliberately NOT -o pipefail, for the same reason scan.sh omits it: almost
# every pipeline here ends in a grep that legitimately finds nothing, or a find across
# directories that refuse permission. Under pipefail a clean "no links found" becomes a
# hard failure. Producer failures surface as empty output, which is visible and safe.
set -eu

die() { echo "link-guard.sh: $*" >&2; exit 1; }

TARGET_RAW="${1:-}"
MANIFEST="${2:-}"
[ -n "$TARGET_RAW" ] || die "usage: link-guard.sh <TARGET-DIR> [LINK-MANIFEST]"
[ -d "$TARGET_RAW" ] || die "not a directory: $TARGET_RAW"

# An app can have stored any of several spellings of the same folder. Collect every
# variant so a reference written as /System/Volumes/Data/Users/... still matches an
# item found under /Users/....
TARGET_L="$(cd "$TARGET_RAW" && pwd)"      # logical (follows symlinks as typed)
TARGET_P="$(cd "$TARGET_RAW" && pwd -P)"   # physical
PREFIXES="$(mktemp -t lg-pref)"
REFS="$(mktemp -t lg-refs)"
HITS="$(mktemp -t lg-hits)"
ITEMS="$(mktemp -t lg-items)"
trap 'rm -f "$PREFIXES" "$REFS" "$HITS" "$ITEMS"' EXIT

# The top-level entries organize-folder would actually consider moving. Mirrors
# safe-sort.sh's skip set: this run's own artifacts and every dotfile stay put, so
# they never need a link verdict.
list_items() {
  find "$TARGET_P" -maxdepth 1 -mindepth 1 -print 2>/dev/null \
    | awk -v p="$TARGET_P/" 'index($0,p)==1 { print substr($0, length(p)+1) }' \
    | grep -v '^\.' \
    | grep -v '^_ORGANIZE_' \
    | grep -v '^_UNDO_' \
    | LC_ALL=C sort
}

{ printf '%s\n' "$TARGET_L" "$TARGET_P"
  # firmlink twin: /Users/x <-> /System/Volumes/Data/Users/x
  case "$TARGET_P" in
    /System/Volumes/Data/*) printf '%s\n' "${TARGET_P#/System/Volumes/Data}" ;;
    /*)                     printf '%s\n' "/System/Volumes/Data$TARGET_P" ;;
  esac
} | sed 's:/*$::' | grep -v '^$' | LC_ALL=C sort -u > "$PREFIXES"

MODE=""; SOURCE=""

# ---------------------------------------------------------------------------
# Mode A — a system-audit link manifest was handed in. This is the natural handoff
# and by far the cheapest path: the expensive sweep already happened during the audit.
if [ -n "$MANIFEST" ]; then
  [ -f "$MANIFEST" ] || die "no such manifest: $MANIFEST"
  MODE="manifest"; SOURCE="$MANIFEST"
  # Normalize every accepted shape down to  app<TAB>path.
  awk -F'\t' '
    {
      app="-"; p=""
      if (NF >= 3 && ($2 == "[OK]" || $2 == "[MISSING]")) { app=$1; p=$3 }
      else if (NF >= 2 && ($1 == "[OK]" || $1 == "[MISSING]")) { p=$2 }
      else if (substr($1,1,1) == "/") { p=$1 }
      else if (NF >= 2 && substr($2,1,1) == "/") { app=$1; p=$2 }
      if (p == "") next
      sub(/[ \t]+$/, "", p)
      if (substr(p,1,1) != "/") next
      print app "\t" p
    }' "$MANIFEST" | LC_ALL=C sort -u > "$REFS"

# ---------------------------------------------------------------------------
# Mode B — no manifest. Do NOT assume clear. Run a scoped self-check.
#
# Why this shape and not `scan.sh linkindex`: linkindex sweeps every app store and
# `strings`-extracts EVERY external path on the machine — minutes, tens of thousands
# of lines, almost all of it irrelevant to one folder. Here we only care about paths
# under TARGET, so:
#   1. cheap fixed-string grep -l for the TARGET prefix (and its percent-encoded form)
#      across app stores — this is the only full pass, and it reads, never extracts;
#   2. `strings` only the handful of files that matched;
#   3. keep only decoded paths that actually sit under TARGET.
# Same guarantee as linkindex for this folder, a fraction of the cost. Result is
# cached per-target so a preview and the real run don't pay for it twice.
else
  MODE="selfcheck"
  CACHE_DIR="${LINK_GUARD_CACHE_DIR:-$HOME/Library/Caches/link-guard}"
  TTL="${LINK_GUARD_TTL:-86400}"
  mkdir -p "$CACHE_DIR" 2>/dev/null || true
  KEY="$(printf '%s' "$TARGET_P" | md5 -q 2>/dev/null || printf '%s' "$TARGET_P" | md5sum | cut -d' ' -f1)"
  CACHE="$CACHE_DIR/$KEY.refs"

  fresh=0
  if [ "${LINK_GUARD_REFRESH:-0}" != "1" ] && [ -f "$CACHE" ]; then
    age=$(( $(date +%s) - $(stat -f %m "$CACHE" 2>/dev/null || echo 0) ))
    [ "$age" -lt "$TTL" ] && fresh=1
  fi

  if [ "$fresh" = 1 ]; then
    cp "$CACHE" "$REFS"; MODE="cache"; SOURCE="$CACHE (age ${age}s)"
  else
    SOURCE="scoped sweep of ~/Library app stores"
    # Where macOS apps actually keep references. Override with a newline- or
    # colon-separated LINK_GUARD_STORES to scope the sweep to one suspect app
    # (or to point it at a fixture instead of the real Library).
    if [ -n "${LINK_GUARD_STORES:-}" ]; then
      STORES="$(printf '%s' "$LINK_GUARD_STORES" | tr ':' '\n')"
      SOURCE="scoped sweep of LINK_GUARD_STORES"
    else
      STORES="$HOME/Library/Application Support
$HOME/Library/Containers
$HOME/Library/Group Containers
$HOME/Library/Preferences
$HOME/Library/Saved Application State"
    fi

    # Percent-encoded twin: many apps store file:// URLs. Only spaces matter in
    # practice for a folder path, and grep -F wants a literal, so build both.
    scanned=0
    : > "$HITS"
    while IFS= read -r store; do
      [ -d "$store" ] || continue
      [ -r "$store" ] || continue
      # Prune the caches inside the stores: stale copies, minutes of cost, no truth.
      files="$(find "$store" -type d \( -iname 'Cache*' -o -iname '*Caches' -o -iname 'Code Cache' \
                 -o -iname 'GPUCache' -o -iname 'Service Worker' -o -iname 'IndexedDB' \
                 -o -iname 'logs' -o -iname 'Logs' -o -iname 'Crashpad' \) -prune -o \
                 -type f -size -20M -print 2>/dev/null | wc -l | tr -d ' ')"
      scanned=$((scanned + files))
      while IFS= read -r pfx; do
        enc="$(printf '%s' "$pfx" | sed 's/ /%20/g')"
        find "$store" -type d \( -iname 'Cache*' -o -iname '*Caches' -o -iname 'Code Cache' \
             -o -iname 'GPUCache' -o -iname 'Service Worker' -o -iname 'IndexedDB' \
             -o -iname 'logs' -o -iname 'Logs' -o -iname 'Crashpad' \) -prune -o \
             -type f -size -20M -print0 2>/dev/null \
          | xargs -0 grep -laF -e "$pfx/" -e "$enc/" 2>/dev/null >> "$HITS" || true
      done < "$PREFIXES"
    done <<EOF
$STORES
EOF

    # Zero readable files across every store is not "no links" — it is "we were not
    # allowed to look" (TCC / Full Disk Access, the exact failure that made the
    # scheduled organize-folder job report a cheerful moved=0 for a month). Refuse to
    # call that a clean result.
    if [ "$scanned" -eq 0 ]; then
      list_items > "$ITEMS" || true
      while IFS= read -r item; do
        printf 'UNKNOWN\t%s\t0\t(app stores unreadable — grant Full Disk Access)\n' "$item"
      done < "$ITEMS"
      printf '@MODE\tselfcheck\n@SOURCE\tapp stores unreadable\n@BLOCKED\t0\n@CLEAR\t0\n@UNKNOWN\tall\n'
      exit 2
    fi

    LC_ALL=C sort -u "$HITS" -o "$HITS"
    : > "$REFS"
    while IFS= read -r hit; do
      [ -n "$hit" ] || continue
      # Attribute the hit to an app the way scan.sh trace does: first path segment
      # under the store root.
      case "$hit" in
        "$HOME/Library/"*)
          rest="${hit#"$HOME"/Library/}"; rest="${rest#*/}"; owner="${rest%%/*}" ;;
        *) owner="$(basename "$(dirname "$hit")")" ;;
      esac
      owner="${owner%.plist}"
      strings -a "$hit" 2>/dev/null \
        | grep -oE '(file://)?/[^"<>|*?\\]{3,250}' \
        | sed -e 's|^file://||' \
        | perl -pe 's/%([0-9A-Fa-f]{2})/chr(hex($1))/ge' \
        | sed -e 's/[[:space:]]*$//' -e 's/[`'"'"'",;)]*$//' \
        | grep -v '`' \
        | LC_ALL=C sort -u \
        | while IFS= read -r p; do
            printf '%s\t%s\n' "${owner:-?}" "$p"
          done >> "$REFS" || true
    done < "$HITS"
    LC_ALL=C sort -u "$REFS" -o "$REFS"
    cp "$REFS" "$CACHE" 2>/dev/null || true
  fi
fi

# ---------------------------------------------------------------------------
# Salvage, then bucket each reference under the top-level item it lands in.
#
# Salvage is the same trick report_path() uses in scan.sh: real paths contain spaces,
# so the extraction regex has to allow them, which means it also swallows whatever
# followed the path in the binary blob. Trim trailing space-delimited tokens until
# something on disk resolves. Here it matters in ONE direction only — a reference we
# fail to resolve is a reference we do not count, and an uncounted reference is a
# file we might move. So bias every ambiguous call toward BLOCKED.
awk -F'\t' -v OFS='\t' '
  NR==FNR { pref[FNR]=$0; np=FNR; next }
  {
    app=$1; p=$2
    for (i=1; i<=np; i++) {
      pl = length(pref[i])
      if (substr(p, 1, pl+1) == pref[i] "/") {
        rest = substr(p, pl+2)
        k = index(rest, "/")
        item = (k > 0) ? substr(rest, 1, k-1) : rest
        if (item != "") print item, app, p
        break
      }
    }
  }' "$PREFIXES" "$REFS" \
  | LC_ALL=C sort -u > "$HITS"

# Salvage pass. A reference that terminates AT the item (rather than inside it) can
# carry trailing junk the extractor swallowed out of the surrounding blob — "PRO 7
# MEDIA" arrives as "PRO 7 MEDIA \b\x00pv". Trim trailing space-delimited tokens
# until the name resolves against a real entry in TARGET. First hit wins; a genuinely
# spaced name resolves on the untrimmed pass and never enters the loop. Without this,
# junk turns a BLOCKED item into a CLEAR one, which is the one error direction that
# actually loses data.
RES="$(mktemp -t lg-res)"
trap 'rm -f "$PREFIXES" "$REFS" "$HITS" "$ITEMS" "$RES" "${AGG:-}"' EXIT
: > "$RES"
while IFS="$(printf '\t')" read -r item app ref; do
  [ -n "$item" ] || continue
  if [ ! -e "$TARGET_P/$item" ] && [ ! -L "$TARGET_P/$item" ]; then
    try="$item"; i=0
    while [ "$i" -lt 8 ]; do
      case "$try" in *" "*) ;; *) break ;; esac
      try="${try% *}"; [ -n "$try" ] || break
      if [ -e "$TARGET_P/$try" ] || [ -L "$TARGET_P/$try" ]; then item="$try"; break; fi
      i=$((i+1))
    done
  fi
  printf '%s\t%s\t%s\n' "$item" "$app" "$ref"
done < "$HITS" | LC_ALL=C sort -u > "$RES"
mv -f "$RES" "$HITS"

# item -> refcount + distinct apps
AGG="$(mktemp -t lg-agg)"
awk -F'\t' '
  { if (!refseen[$1 SUBSEP $3]++) n[$1]++
    if (!appseen[$1 SUBSEP $2]++) apps[$1] = (apps[$1] == "" ? $2 : apps[$1] "," $2) }
  END { for (i in n) printf "%s\t%d\t%s\n", i, n[i], apps[i] }' "$HITS" \
  | LC_ALL=C sort > "$AGG"

list_items > "$ITEMS" || true

printf 'STATUS\tITEM\tREFS\tAPPS\n'
blocked=0; clear=0
while IFS= read -r item; do
  line="$(awk -F'\t' -v it="$item" '$1==it {print; exit}' "$AGG")"
  if [ -n "$line" ]; then
    refs="$(printf '%s' "$line" | cut -f2)"
    apps="$(printf '%s' "$line" | cut -f3)"
    [ "$apps" = "-" ] && apps="(referencing app not recorded in manifest)"
    printf 'BLOCKED\t%s\t%s\t%s\n' "$item" "$refs" "$apps"
    blocked=$((blocked+1))
  else
    printf 'CLEAR\t%s\t0\t-\n' "$item"
    clear=$((clear+1))
  fi
done < "$ITEMS"

printf '@MODE\t%s\n@SOURCE\t%s\n@BLOCKED\t%d\n@CLEAR\t%d\n@UNKNOWN\t0\n' \
       "$MODE" "$SOURCE" "$blocked" "$clear"
