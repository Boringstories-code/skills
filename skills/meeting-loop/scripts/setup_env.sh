#!/usr/bin/env bash
# setup_env.sh — ensure the persistent, machine-local transcription venv exists.
#
# Creates ~/.cache/mlx-whisper-transcribe/venv ($CML_ENV_DIR wins) on first run with
# $CML_PYTHON (default python3) and installs the deps transcribe.py and local_model.py
# need, pinned to the set tested together on Apple's Python 3.9 (mlx-lm 0.32+ needs
# Python 3.11+). Idempotent: re-running is a fast no-op
# once the venv is healthy. This venv is intentionally NOT in the synced vault;
# on a fresh Mac it rebuilds itself the first time the skill runs.
#
# Prints the python interpreter path on the last line (stdout) so callers can
# capture it: PY="$(scripts/setup_env.sh | tail -1)"
set -uo pipefail

ENV_DIR="${CML_ENV_DIR:-$HOME/.cache/mlx-whisper-transcribe/venv}"
PY="$ENV_DIR/bin/python"
BASE_PY="${CML_PYTHON:-python3}"
PINS="mlx==0.29.3 mlx-whisper==0.4.3 mlx-lm==0.28.4 huggingface_hub==0.36.2 transformers==4.57.6 soundfile==0.13.1 scipy==1.13.1 numpy==2.0.2"

healthy() {
  [ -x "$PY" ] && "$PY" -c "import mlx_whisper, mlx_lm, soundfile, scipy, numpy" >/dev/null 2>&1
}

if healthy; then
  echo "[setup] venv healthy: $ENV_DIR" >&2
  echo "$PY"
  exit 0
fi

echo "[setup] creating venv at $ENV_DIR (first run / repair)..." >&2
mkdir -p "$(dirname "$ENV_DIR")"
"$BASE_PY" -m venv "$ENV_DIR" || { echo "[setup] venv creation failed" >&2; exit 1; }
"$PY" -m pip install --upgrade pip -q >&2
"$PY" -m pip install -q $PINS >&2 || { echo "[setup] pip install failed" >&2; exit 1; }

if healthy; then
  echo "[setup] done." >&2
  echo "$PY"
else
  echo "[setup] venv still unhealthy after install" >&2
  exit 1
fi
