#!/usr/bin/env bash
# selftest.sh — exercise the meeting-loop engine end to end so a broken edit is
# caught here, not in a real meeting. Also the adoption on-ramp: run it once and
# you know the machine is wired correctly.
#
#   scripts/selftest.sh          fast: compile + venv + ffmpeg convert + two-mic
#                                diarize + HTML render (no model downloads)
#   scripts/selftest.sh --asr    also run a real Whisper transcription + the
#                                resumability skip + --prompt priming
#   scripts/selftest.sh --diar   also attempt single-mic pyannote (needs
#                                setup_diarization.sh + cached model)
#   scripts/selftest.sh --asr --diar   everything
#
# Uses a scratch dir under TMPDIR; cleans up on exit. Needs ffmpeg on PATH.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DO_ASR=0; DO_DIAR=0
for a in "$@"; do
  case "$a" in
    --asr) DO_ASR=1 ;;
    --diar) DO_DIAR=1 ;;
    *) echo "unknown flag: $a" >&2; exit 2 ;;
  esac
done

PASS=0; FAIL=0
ok()  { echo "  PASS  $1"; PASS=$((PASS+1)); }
bad() { echo "  FAIL  $1"; FAIL=$((FAIL+1)); }
have(){ command -v "$1" >/dev/null 2>&1; }

WORK="$(mktemp -d "${TMPDIR:-/tmp}/mtgloop-selftest.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT
echo "[selftest] scratch: $WORK"

echo "== 1. syntax =="
for f in "$HERE"/*.py; do
  if python3 -m py_compile "$f" 2>/dev/null; then ok "py_compile $(basename "$f")"; else bad "py_compile $(basename "$f")"; fi
done
for f in "$HERE"/*.sh; do
  if bash -n "$f" 2>/dev/null; then ok "bash -n $(basename "$f")"; else bad "bash -n $(basename "$f")"; fi
done

echo "== 2. prerequisites =="
if have ffmpeg; then ok "ffmpeg present"; else bad "ffmpeg missing (brew install ffmpeg)"; fi

echo "== 3. base venv =="
PY="$(bash "$HERE/setup_env.sh" 2>/dev/null | tail -1)"
if [ -x "$PY" ] && "$PY" -c "import soundfile,numpy,scipy" 2>/dev/null; then ok "venv healthy ($PY)"; else bad "venv unhealthy"; PY=""; fi

echo "== 4b. sample_for_grouping (start/mid/end windows) =="
if have ffmpeg && python3 "$HERE/sample_for_grouping.py" --selftest >/dev/null 2>&1; then
  ok "sample_for_grouping"
else bad "sample_for_grouping"; fi

echo "== 4. ffmpeg m4a -> wav, soundfile-readable =="
if have ffmpeg; then
  ffmpeg -y -f lavfi -i "sine=frequency=440:duration=2" -c:a aac "$WORK/a.m4a" >/dev/null 2>&1
  ffmpeg -y -i "$WORK/a.m4a" -ac 1 -ar 16000 -c:a pcm_s16le "$WORK/a.wav" >/dev/null 2>&1
  if [ -n "$PY" ] && "$PY" -c "import soundfile as sf; a,sr=sf.read('$WORK/a.wav'); assert sr==16000 and a.ndim==1" 2>/dev/null; then
    ok "m4a converted to 16k mono wav"
  else bad "m4a convert/read"; fi
else bad "skipped (no ffmpeg)"; fi

echo "== 5. HTML render (brand + payload) =="
if [ -n "$PY" ]; then
  cat > "$WORK/ai.json" <<'JSON'
{"title":"Selftest","brand":"generic","date":"2026-01-01",
 "sections":[{"heading":"Tasks","kind":"tasks","items":[{"task":"do x","detail":"note"}]},
 {"heading":"Notes","kind":"notes","items":[{"title":"t","body":"MARKER_BODY"}]}]}
JSON
  "$PY" "$HERE/render_action_items_html.py" "$WORK/ai.json" "$WORK/ai.html" >/dev/null 2>&1
  if grep -q "MARKER_BODY" "$WORK/ai.html" 2>/dev/null && [ "$(wc -c < "$WORK/ai.html")" -gt 2000 ]; then
    ok "rendered self-contained HTML"
  else bad "HTML render"; fi
else bad "skipped (no venv)"; fi

echo "== 5b. AI handoff render (waves + index) =="
if [ ! -f "$HERE/handoff_render.py" ]; then
  echo "  skip  handoff_render.py isn't part of this tree"
else
if python3 "$HERE/handoff_render.py" --selftest 2>/dev/null | grep -q "waves OK"; then ok "handoff waves"; else bad "handoff waves"; fi
cat > "$WORK/ho.json" <<'JSON'
{"meeting":{"date":"2026-01-01","topic":"selftest","type":"work"},"owner":"Test","default_target":"claude",
 "grill":{"questions":[{"id":"Q1","title":"t","body":"b","recommended":"r","blocks":[2]}]},
 "items":[{"id":1,"target":"claude","type":"content","task":"a","quote":"have Claude do a","speaker":"Test","size":"quick fix","capability":"c"},
          {"id":2,"target":"codex","type":"comms","task":"b","quote":"then email it","speaker":"Test","size":"quick fix","capability":"c","one_way_door":true,"privacy":"local-only","depends_on":[1]}],
 "inferred":[]}
JSON
if python3 "$HERE/handoff_render.py" "$WORK/ho.json" --queue "$WORK/queue" >/dev/null 2>&1 \
   && grep -q "Wave 2:.*#2.*one-way door" "$WORK/ho.md" \
   && grep -q "local-only and were withheld" "$WORK/ho.md" \
   && grep -q "| selftest | work | - | claude,codex | 0/2 | 2 | open |" "$WORK/queue/INDEX.md"; then ok "handoff render + index"; else bad "handoff render + index"; fi
if python3 "$HERE/handoff_render.py" "$WORK/ho.json" --queue "$WORK/queue" --status done >/dev/null 2>&1 \
   && grep -q "| 2/2 | 2 | done |" "$WORK/queue/INDEX.md"; then ok "handoff self-close"; else bad "handoff self-close"; fi
if python3 "$HERE/handoff_render.py" --selftest 2>/dev/null | grep -q "merge OK"; then ok "handoff merge math"; else bad "handoff merge math"; fi
mkdir -p "$WORK/m1" "$WORK/m2"
cat > "$WORK/m1/ai-handoff.json" <<'JSON'
{"meeting":{"date":"2026-01-01","topic":"g-mon","type":"work","group":"g"},"owner":"T","items":[{"id":1,"target":"claude","type":"content","task":"Build the deck","quote":"make the deck","speaker":"T","size":"quick fix"},{"id":2,"target":"claude","type":"comms","task":"Email the deck","quote":"email it","speaker":"T","size":"quick fix","one_way_door":true,"depends_on":[1]}],"grill":{"questions":[]},"inferred":[]}
JSON
cat > "$WORK/m2/ai-handoff.json" <<'JSON'
{"meeting":{"date":"2026-01-03","topic":"g-wed","type":"work","group":"g"},"owner":"T","items":[{"id":1,"target":"claude","type":"content","task":"Build the deck","quote":"deck done yet","speaker":"T","size":"feature"},{"id":2,"target":"grok","type":"research","task":"Pull comps","quote":"ask grok","speaker":"T","size":"quick fix"}],"grill":{"questions":[]},"inferred":[]}
JSON
python3 "$HERE/handoff_render.py" "$WORK/m1/ai-handoff.json" --queue "$WORK/queue" >/dev/null 2>&1
python3 "$HERE/handoff_render.py" "$WORK/m2/ai-handoff.json" --queue "$WORK/queue" >/dev/null 2>&1
if python3 "$HERE/handoff_render.py" --merge-group g --queue "$WORK/queue" --out-dir "$WORK/merged" 2>&1 | grep -q "4 items → 3 kept + 1 folded" \
   && grep -q "Reconciliation:.*4 source items = 3 kept + 1 folded" "$WORK/merged/ai-handoff.merged.md" \
   && grep -q "| merged-g | work | g |" "$WORK/queue/INDEX.md"; then ok "handoff merge-group + timeline"; else bad "handoff merge-group + timeline"; fi
if python3 "$HERE/handoff_render.py" "$WORK/merged/ai-handoff.merged.json" --queue "$WORK/queue" --status done >/dev/null 2>&1 \
   && [ "$(grep -c '| done |' "$WORK/queue/INDEX.md")" -ge 3 ]; then ok "handoff merged done → sources done"; else bad "handoff merged done → sources done"; fi
fi

echo "== 6. two-mic diarize (synthetic) =="
if [ -n "$PY" ] && have ffmpeg; then
  # two mono files: A loud 0-1s silent 1-2s, B silent 0-1s loud 1-2s
  ffmpeg -y -f lavfi -i "sine=frequency=300:duration=1" -f lavfi -i "anullsrc=r=16000:cl=mono:d=1" \
    -filter_complex "[0][1]concat=n=2:v=0:a=1" -ar 16000 -ac 1 "$WORK/A.wav" >/dev/null 2>&1
  ffmpeg -y -f lavfi -i "anullsrc=r=16000:cl=mono:d=1" -f lavfi -i "sine=frequency=300:duration=1" \
    -filter_complex "[0][1]concat=n=2:v=0:a=1" -ar 16000 -ac 1 "$WORK/B.wav" >/dev/null 2>&1
  printf '[00:00:00.000 -> 00:00:01.000] hello from A\n[00:00:01.000 -> 00:00:02.000] hello from B\n' > "$WORK/A.segments.txt"
  "$PY" "$HERE/diarize_two_mic.py" --spine "$WORK/A.wav" --other "$WORK/B.wav" \
    --spine-segments "$WORK/A.segments.txt" --name-spine Alice --name-other Bob \
    --out "$WORK/A.attr.txt" >/dev/null 2>&1
  if grep -qE '\] (Alice|Bob): ' "$WORK/A.attr.txt" 2>/dev/null; then ok "two-mic attributed output"; else bad "two-mic diarize"; fi
else bad "skipped (no venv/ffmpeg)"; fi

if [ "$DO_ASR" = 1 ]; then
  echo "== 7. Whisper ASR + resume + prompt (real model) =="
  if [ -n "$PY" ] && [ -f "$WORK/a.wav" ]; then
    "$PY" "$HERE/transcribe.py" "$WORK/a.wav" "$WORK/t" --prompt "Acme Widget" >/dev/null 2>&1
    if [ -s "$WORK/t.json" ] && [ -s "$WORK/t.segments.txt" ]; then ok "transcribe wrote outputs"; else bad "transcribe outputs"; fi
    if "$PY" "$HERE/transcribe.py" "$WORK/a.wav" "$WORK/t" 2>&1 | grep -q "\[skip\]"; then ok "resumability skip on rerun"; else bad "resumability skip"; fi
    # m4a path through transcribe (auto-convert)
    if "$PY" "$HERE/transcribe.py" "$WORK/a.m4a" "$WORK/tm4a" --force >/dev/null 2>&1 && [ -s "$WORK/tm4a.json" ]; then ok "transcribe m4a via auto-convert"; else bad "transcribe m4a"; fi
  else bad "skipped (no venv)"; fi
fi

if [ "$DO_DIAR" = 1 ]; then
  echo "== 8. single-mic pyannote (attempt) =="
  if [ -n "$PY" ] && "$PY" -c "import pyannote.audio" 2>/dev/null; then
    if [ -f "$WORK/a.wav" ]; then
      printf '[00:00:00.000 -> 00:00:02.000] test line\n' > "$WORK/a.segments.txt"
      if "$PY" "$HERE/diarize_single_mic.py" --audio "$WORK/a.wav" --segments "$WORK/a.segments.txt" --out "$WORK/a.sm.txt" 2>&1 | grep -qiE "wrote|error"; then
        if grep -qE '\] [^ ]+: ' "$WORK/a.sm.txt" 2>/dev/null; then ok "single-mic attributed output"; else bad "single-mic output format (model may be un-accepted/uncached)"; fi
      else bad "single-mic run"; fi
    fi
  else bad "pyannote not installed — run setup_diarization.sh (skipping)"; fi
fi

echo
echo "[selftest] PASS=$PASS FAIL=$FAIL"
[ "$FAIL" -eq 0 ]
