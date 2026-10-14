#!/usr/bin/env bash
# audit-tool / scan.sh — static security scanner for Claude skills, plugins, MCP servers, and tools.
#
# STATIC ANALYSIS ONLY. This never executes a single line of the target. It reads files
# and matches patterns. That is the whole point: you audit untrusted code WITHOUT running it.
#
# Usage:   scan.sh <path-to-skill-or-tool-dir-or-file>
# Output:  a severity-ranked findings report on stdout, ending in a machine-parseable
#          SUMMARY line: SUMMARY CRITICAL=<n> HIGH=<n> MEDIUM=<n> LOW=<n> FILES=<n> BINARIES=<n>
# Exit:    0 if no CRITICAL/HIGH findings, 2 if any CRITICAL/HIGH, 1 on usage error.
#
# Dependency-free: bash + grep + find + standard coreutils. No jq, no python, no network.

set -u

TARGET="${1:-}"
if [[ -z "$TARGET" || ! -e "$TARGET" ]]; then
  echo "usage: scan.sh <path-to-skill/tool dir or file>" >&2
  exit 1
fi

SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KNOWN_BAD="$SELF_DIR/../references/known-bad.txt"

C=0; H=0; M=0; L=0; NFILES=0; NBIN=0

# Buffers per severity so the report reads top-down by danger.
CRIT_OUT=""; HIGH_OUT=""; MED_OUT=""; LOW_OUT=""

emit() { # emit <SEV> <category> <file> <line> <snippet>
  local sev="$1" cat="$2" file="$3" ln="$4" snip="$5"
  # Documentation can't EXECUTE. A dangerous execution/access pattern shown in prose
  # (.md/.txt/.rst) is informational — surface it for review, don't hard-block on it.
  # Downgrade one level for those categories only. Signature/destination/injection/
  # hidden-content patterns stay at full severity anywhere (dangerous as data, not code).
  case "$file" in
    *.md|*.markdown|*.mdx|*.rst|*.txt)
      case " SECRET-ACCESS PIPE-TO-SHELL REVERSE-SHELL DESTRUCTIVE ENCODED-EXEC OBFUSCATION NPM-LIFECYCLE PY-INSTALL PERSISTENCE PRIVILEGE ENV-HARVEST KEYCHAIN BASE64-BLOB HARDCODED-IP SELF-MODIFY " in
        *" $cat "*)
          if   [ "$sev" = CRITICAL ]; then sev=HIGH;   cat="$cat(doc)"
          elif [ "$sev" = HIGH ];     then sev=MEDIUM; cat="$cat(doc)"; fi ;;
      esac ;;
  esac
  # trim + clamp snippet
  snip="$(printf '%s' "$snip" | tr -d '\r' | sed 's/^[[:space:]]*//' | cut -c1-160)"
  local rel="${file#"$TARGET"/}"
  local line="  [$cat] $rel:$ln  →  $snip"
  case "$sev" in
    CRITICAL) CRIT_OUT+="$line"$'\n'; C=$((C+1));;
    HIGH)     HIGH_OUT+="$line"$'\n'; H=$((H+1));;
    MEDIUM)   MED_OUT+="$line"$'\n';  M=$((M+1));;
    *)        LOW_OUT+="$line"$'\n';  L=$((L+1));;
  esac
}

# grep a pattern group across one file; emit each hit at a given severity/category.
scan_file_pat() { # scan_file_pat <sev> <category> <file> <ERE-pattern>
  local sev="$1" cat="$2" file="$3" pat="$4" hit
  # -I skips binary, -n line numbers, -E ERE, -i case-insensitive
  while IFS= read -r hit; do
    [[ -z "$hit" ]] && continue
    local ln="${hit%%:*}"
    local snip="${hit#*:}"
    emit "$sev" "$cat" "$file" "$ln" "$snip"
  done < <(grep -IinE "$pat" "$file" 2>/dev/null)
}

is_text() { grep -qI . "$1" 2>/dev/null; }

# ---- collect file list (skip vcs / vendored noise, but FLAG vendored dirs separately) ----
# Portable to bash 3.2 (no mapfile). Filenames with embedded newlines are not expected in skills.
ALLFILES=()
while IFS= read -r _line; do
  [[ -n "$_line" ]] && ALLFILES+=("$_line")
done < <(find "$TARGET" -type f \
  -not -path '*/.git/*' \
  -not -path '*/node_modules/*' \
  -not -path '*/.venv/*' -not -path '*/venv/*' \
  2>/dev/null)

# Flag the mere presence of shipped dependencies/binaries — a skill should not ship these.
if find "$TARGET" -type d -name node_modules 2>/dev/null | grep -q .; then
  emit MEDIUM SHIPPED-DEPS "$TARGET" 0 "ships a node_modules/ dir — review why a skill bundles dependencies"
fi
if find "$TARGET" -type d \( -name venv -o -name .venv \) 2>/dev/null | grep -q .; then
  emit MEDIUM SHIPPED-DEPS "$TARGET" 0 "ships a python virtualenv — review why"
fi

for f in ${ALLFILES[@]+"${ALLFILES[@]}"}; do
  NFILES=$((NFILES+1))
  if ! is_text "$f"; then
    NBIN=$((NBIN+1))
    emit HIGH BINARY "$f" 0 "binary/executable shipped inside a skill — cannot be statically reviewed, treat as opaque"
    continue
  fi

  base="$(basename "$f")"

  # ============ A. SECRET / CREDENTIAL ACCESS ============
  scan_file_pat CRITICAL SECRET-ACCESS "$f" \
    '(\.ssh/|id_rsa|id_ed25519|\.aws/credentials|\.config/gcloud|\.netrc|\.git-credentials|\.npmrc|\.docker/config|/Library/Keychains|security[[:space:]]+(find|dump)-.*-password|\.claude/\.credentials|\.claude\.json|Login Data|Cookies\.binarycookies|/Cookies)'
  scan_file_pat HIGH ENV-HARVEST "$f" \
    '(printenv|env[[:space:]]*\||os\.environ(\.items|\b.*for)|dict\(os\.environ\)|JSON\.stringify\(process\.env\)|Object\.entries\(process\.env\))'
  scan_file_pat HIGH KEYCHAIN "$f" \
    '(keychain|security[[:space:]]+find-generic-password|defaults[[:space:]]+read.*password|gnome-keyring|secret-tool)'

  # ============ B. NETWORK CALLOUTS / EXFIL ============
  scan_file_pat HIGH NETWORK "$f" \
    '(curl[[:space:]]|wget[[:space:]]|requests\.(post|get|put)|urllib\.|http\.client|fetch\(|XMLHttpRequest|axios\.|net\.Socket|socket\.socket|Invoke-WebRequest)'
  scan_file_pat CRITICAL EXFIL-DEST "$f" \
    '(webhook\.site|requestbin|pipedream|ngrok\.io|\.tk/|\.ru/|pastebin\.com|hastebin|discord(app)?\.com/api/webhooks|api\.telegram\.org/bot|transfer\.sh|file\.io)'
  scan_file_pat CRITICAL REVERSE-SHELL "$f" \
    '(/dev/tcp/|bash[[:space:]]+-i|nc[[:space:]]+-e|ncat[[:space:]]+-e|sh[[:space:]]+-i|socket\.socket.*connect|pty\.spawn|powershell[[:space:]]+-enc)'
  # hardcoded raw IP:port
  scan_file_pat MEDIUM HARDCODED-IP "$f" \
    '([0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}:[0-9]{2,5})'

  # ============ C. OBFUSCATION & PIPE-TO-SHELL ============
  scan_file_pat CRITICAL PIPE-TO-SHELL "$f" \
    '((curl|wget)[^|]*\|[[:space:]]*(sudo[[:space:]]+)?(ba)?sh|base64[[:space:]]+(-d|--decode)[^|]*\|[[:space:]]*(ba)?sh|\|[[:space:]]*(ba)?sh[[:space:]]*-)'
  scan_file_pat HIGH OBFUSCATION "$f" \
    '(eval\(atob\(|eval\(base64|exec\(base64|eval\([[:space:]]*(decode|unescape|fromCharCode)|Function\([[:space:]]*["'"'"']return|iex\(|\\x[0-9a-f]{2}\\x[0-9a-f]{2}\\x[0-9a-f]{2})'
  scan_file_pat MEDIUM ENCODED-EXEC "$f" \
    '(eval\(|[^.]exec\(|child_process|subprocess\.(Popen|call|run)|os\.system|popen\(|spawnSync|execSync)'

  # long base64-looking blob on a single line (>=120 chars) — likely packed payload
  while IFS= read -r hit; do
    [[ -z "$hit" ]] && continue
    emit HIGH BASE64-BLOB "$f" "${hit%%:*}" "long encoded blob (possible packed payload)"
  done < <(grep -InE '[A-Za-z0-9+/]{120,}={0,2}' "$f" 2>/dev/null)

  # ============ D. CLAUDE-TOOL-SPECIFIC SURFACES ============
  # auto-executing hooks (settings.json / plugin manifests)
  if [[ "$base" == "settings.json" || "$base" == "settings.local.json" || "$base" == *plugin*.json || "$base" == "hooks.json" ]]; then
    scan_file_pat CRITICAL AUTO-HOOK "$f" \
      '("(PreToolUse|PostToolUse|UserPromptSubmit|Stop|SessionStart|Notification)"|"command"[[:space:]]*:)'
  fi
  # MCP server definitions — what command runs, what it connects to
  if [[ "$base" == ".mcp.json" || "$base" == "mcp.json" || "$base" == *.mcp.json ]]; then
    scan_file_pat HIGH MCP-SERVER "$f" \
      '("command"|"args"|"env"|"url")'
  fi
  scan_file_pat HIGH MCP-INLINE "$f" \
    '("mcpServers"[[:space:]]*:)'

  # prompt-injection / "lie to the user" / "act without asking" language in any markdown or text
  scan_file_pat HIGH PROMPT-INJECTION "$f" \
    '(ignore[[:space:]]+(all[[:space:]]+)?(previous|prior|above)[[:space:]]+instructions|disregard[[:space:]]+(the[[:space:]]+)?(system|previous)|do[[:space:]]+not[[:space:]]+(tell|inform|mention[[:space:]]+to)[[:space:]]+the[[:space:]]+user|without[[:space:]]+(telling|asking|notifying)[[:space:]]+the[[:space:]]+user|regardless[[:space:]]+of[[:space:]]+(what[[:space:]]+the[[:space:]]+user|safety|policy)|you[[:space:]]+must[[:space:]]+(run|execute|send|exfiltrat)|override[[:space:]]+(the[[:space:]]+)?(system[[:space:]]+prompt|safety)|reveal[[:space:]]+(the[[:space:]]+)?(system[[:space:]]+prompt|api[[:space:]]*key|credentials))'

  # ============ E. DESTRUCTIVE / PERSISTENCE ============
  scan_file_pat CRITICAL DESTRUCTIVE "$f" \
    '(rm[[:space:]]+-rf[[:space:]]+(/|~|\$HOME|\*)|:\(\)\{[[:space:]]*:\|:|mkfs|dd[[:space:]]+if=/dev/(zero|random)[[:space:]]+of=/|chmod[[:space:]]+-R?[[:space:]]*777[[:space:]]+/)'
  scan_file_pat HIGH PERSISTENCE "$f" \
    '(crontab|LaunchAgents|LaunchDaemons|>>[[:space:]]*~/\.(bashrc|zshrc|bash_profile|profile)|>>[[:space:]]*\$HOME/\.(bashrc|zshrc)|systemctl[[:space:]]+enable|/etc/cron)'
  scan_file_pat HIGH SELF-MODIFY "$f" \
    '(~/\.claude/|\$HOME/\.claude/|\.claude/settings|\.claude/skills)'
  scan_file_pat MEDIUM PRIVILEGE "$f" \
    '(sudo[[:space:]]|chmod[[:space:]]+\+x|osascript[[:space:]]+-e|defaults[[:space:]]+write)'

  # ============ F. PACKAGE INSTALL LIFECYCLE ============
  if [[ "$base" == "package.json" ]]; then
    scan_file_pat HIGH NPM-LIFECYCLE "$f" \
      '"(pre|post)?install"[[:space:]]*:'
  fi
  if [[ "$base" == "setup.py" || "$base" == "setup.cfg" || "$base" == "pyproject.toml" ]]; then
    scan_file_pat MEDIUM PY-INSTALL "$f" \
      '(cmdclass|install_requires.*git\+|subprocess|os\.system|__import__)'
  fi

  # ============ G. HIDDEN / INVISIBLE UNICODE (injection that the eye can't see) ============
  # zero-width space/joiners, LTR/RTL bidi overrides, word-joiner, BOM mid-file.
  # BSD grep has no -P, so match the raw UTF-8 byte sequences under the C locale:
  #   U+200B-200F, U+202A-202E -> E2 80 8B..8F, AA..AE
  #   U+2060-2064              -> E2 81 A0..A4
  #   U+FEFF (BOM/ZWNBSP)      -> EF BB BF
  while IFS= read -r hit; do
    [[ -z "$hit" ]] && continue
    emit HIGH HIDDEN-UNICODE "$f" "${hit%%:*}" "zero-width / bidi-override unicode (text hidden from a human reader)"
  done < <(LC_ALL=C grep -nE $'\xe2\x80[\x8b-\x8f\xaa-\xae]|\xe2\x81[\xa0-\xa4]|\xef\xbb\xbf' "$f" 2>/dev/null)
done

# ============ H. KNOWN-BAD / TYPOSQUAT MATCH ============
if [[ -f "$KNOWN_BAD" && ${#ALLFILES[@]} -gt 0 ]]; then
  while IFS= read -r bad; do
    bad="${bad%%#*}"; bad="$(printf '%s' "$bad" | tr -d '[:space:]')"
    [[ -z "$bad" ]] && continue
    while IFS= read -r hit; do
      [[ -z "$hit" ]] && continue
      file="${hit%%:*}"; rest="${hit#*:}"; ln="${rest%%:*}"
      emit CRITICAL KNOWN-BAD "$file" "$ln" "matches known-bad / typosquat indicator: $bad"
    done < <(grep -InF -- "$bad" "${ALLFILES[@]}" 2>/dev/null)
  done < "$KNOWN_BAD"
fi

# ---------------- report ----------------
echo "═══════════════════════════════════════════════════════════════"
echo " AUDIT-TOOL static scan"
echo " target : $TARGET"
echo " scanned: $NFILES files  ($NBIN binary/opaque)"
echo "═══════════════════════════════════════════════════════════════"
[[ -n "$CRIT_OUT" ]] && { echo; echo "⛔ CRITICAL ($C)"; printf '%s' "$CRIT_OUT"; }
[[ -n "$HIGH_OUT" ]] && { echo; echo "🔴 HIGH ($H)"; printf '%s' "$HIGH_OUT"; }
[[ -n "$MED_OUT"  ]] && { echo; echo "🟡 MEDIUM ($M)"; printf '%s' "$MED_OUT"; }
[[ -n "$LOW_OUT"  ]] && { echo; echo "⚪ LOW ($L)"; printf '%s' "$LOW_OUT"; }
if (( C+H+M+L == 0 )); then echo; echo "No pattern-level findings. (Still read the SKILL.md and confirm capability matches purpose.)"; fi
echo
echo "SUMMARY CRITICAL=$C HIGH=$H MEDIUM=$M LOW=$L FILES=$NFILES BINARIES=$NBIN"

if (( C+H > 0 )); then exit 2; fi
exit 0
