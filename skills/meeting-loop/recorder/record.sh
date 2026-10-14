#!/usr/bin/env bash
# record.sh — dead-simple mic recorder that feeds the meeting-loop skill.
#
#   record.sh <client-slug> [topic]
#
# Records the default Mac microphone to a 16 kHz mono WAV (exactly what the
# transcribe engine wants) and drops it in a known folder. Press q (or Ctrl-C)
# to stop. Prints the file path on the last line so you can hand it straight to:
#   "run the meeting-loop on <that path>"
#
# No launchd, no background jobs, no Homebrew — just ffmpeg, which is already on
# this Mac. Audio lives OUTSIDE the synced vault (it's big and binary).
#
# Env overrides:
#   REC_DIR   output folder           (default: ~/MeetingRecordings)
#   REC_MIC   avfoundation mic index  (default: auto-detected real mic)
#
# Useful:
#   record.sh --list      show available microphones and exit
#   record.sh --help      this help
set -uo pipefail

REC_DIR="${REC_DIR:-$HOME/MeetingRecordings}"

usage() {
  awk 'NR>=2 && /^#/ {sub(/^# ?/,""); print; next} NR>=2 {exit}' "$0"
  exit "${1:-0}"
}

# --- list the audio inputs ffmpeg can see (index + name) -----------------------
list_mics() {
  ffmpeg -hide_banner -f avfoundation -list_devices true -i "" 2>&1 \
    | awk '/AVFoundation audio devices:/{a=1; next} /AVFoundation video devices:/{a=0} a' \
    | sed -E 's/.*\[([0-9]+)\] (.*)/\1\t\2/' \
    | grep -E '^[0-9]+'$'\t'
}

# --- pick a sensible default mic: first real input, skipping virtual loopbacks --
default_mic() {
  list_mics | awk -F'\t' '
    $2 !~ /BlackHole/ && $2 !~ /The Clock/ && $2 !~ /Virtual/ { print $1; exit }
  '
}

mic_name() {  # mic_name <index>
  list_mics | awk -F'\t' -v i="$1" '$1==i {print $2; exit}'
}

case "${1:-}" in
  -h|--help) usage 0 ;;
  --list)
    echo "Microphones ffmpeg can see (index<TAB>name):"
    list_mics
    exit 0
    ;;
  "") echo "error: client-slug required" >&2; echo; usage 1 ;;
esac

# --- args ---------------------------------------------------------------------
SLUG="$(printf '%s' "$1" | tr '[:upper:] ' '[:lower:]-')"
TOPIC_RAW="${2:-}"
TOPIC="$(printf '%s' "$TOPIC_RAW" | tr '[:upper:] ' '[:lower:]-')"

MIC="${REC_MIC:-$(default_mic)}"
if [ -z "$MIC" ]; then
  echo "error: couldn't find a microphone. Run: record.sh --list" >&2
  exit 1
fi

# --- build the output path ----------------------------------------------------
mkdir -p "$REC_DIR"
STAMP="$(date +%Y-%m-%d-%H%M%S)"
if [ -n "$TOPIC" ]; then
  OUT="$REC_DIR/${SLUG}__${TOPIC}__${STAMP}.wav"
else
  OUT="$REC_DIR/${SLUG}__${STAMP}.wav"
fi

echo "Client : $SLUG${TOPIC:+   Topic: $TOPIC}"
echo "Mic    : [$MIC] $(mic_name "$MIC")"
echo "File   : $OUT"
echo
echo "● Recording… press  q  then Enter to stop  (Ctrl-C also works)."
echo

# 16 kHz mono PCM WAV = ideal for whisper, tiny on disk. ffmpeg stops cleanly on
# 'q' (stdin) or SIGINT and finalizes the WAV header either way.
ffmpeg -hide_banner -loglevel warning -stats \
  -f avfoundation -i ":${MIC}" \
  -ar 16000 -ac 1 -c:a pcm_s16le \
  "$OUT"

echo
if [ -s "$OUT" ]; then
  SIZE="$(du -h "$OUT" | cut -f1)"
  echo "✓ Saved ($SIZE): $OUT"
  echo
  echo "Next: tell Claude →  run the meeting-loop on $OUT"
  echo "$OUT"
else
  echo "✗ No audio captured. Check the mic with: record.sh --list" >&2
  rm -f "$OUT"
  exit 1
fi
