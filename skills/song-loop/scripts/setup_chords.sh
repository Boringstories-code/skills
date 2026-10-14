#!/usr/bin/env bash
# setup_chords.sh — add Spotify Basic Pitch (ONNX) to the meeting-loop whisper
# venv. Kept off the whisper install: only song-loop needs it.
set -uo pipefail

ENV_DIR="${CML_ENV_DIR:-$HOME/.cache/mlx-whisper-transcribe/venv}"
PY="$ENV_DIR/bin/python"

if [ ! -x "$PY" ]; then
  echo "[setup-chords] base venv missing — run Skills/meeting-loop/scripts/setup_env.sh first." >&2
  exit 1
fi

if "$PY" -c "from basic_pitch.inference import predict; import onnxruntime" >/dev/null 2>&1; then
  echo "[setup-chords] basic-pitch already installed: $ENV_DIR" >&2
  echo "$PY"
  exit 0
fi

echo "[setup-chords] installing basic-pitch + onnxruntime (one-time)…" >&2
"$PY" -m pip install -q "basic-pitch>=0.3" onnxruntime >&2 \
  || { echo "[setup-chords] pip install failed" >&2; exit 1; }

if "$PY" -c "from basic_pitch.inference import predict; import onnxruntime" >/dev/null 2>&1; then
  echo "[setup-chords] done." >&2
  echo "$PY"
else
  echo "[setup-chords] still unhealthy after install" >&2
  exit 1
fi
