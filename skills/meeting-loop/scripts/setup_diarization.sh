#!/usr/bin/env bash
# setup_diarization.sh — add single-mic diarization (pyannote.audio) to the
# SAME persistent venv setup_env.sh builds.
#
# Kept SEPARATE from setup_env.sh on purpose: pyannote pulls torch (hundreds of
# MB), and most runs don't need it (two-mic captures use diarize_two_mic.py,
# which needs nothing extra). Run this once, only when you want the single-mic
# fallback. Idempotent: a fast no-op once pyannote imports cleanly.
#
# After install, the pyannote models are HF-gated on FIRST use: accept the terms
# for pyannote/speaker-diarization-3.1 AND pyannote/segmentation-3.0 on
# huggingface.co, then run diarize_single_mic.py once with an HF token
# (--hf-token or env HF_TOKEN). It caches and then runs fully offline.
#
# Prints the python interpreter path on the last line, like setup_env.sh.
set -uo pipefail

ENV_DIR="${CML_ENV_DIR:-$HOME/.cache/mlx-whisper-transcribe/venv}"
PY="$ENV_DIR/bin/python"

if [ ! -x "$PY" ]; then
  echo "[setup-diar] base venv missing — run setup_env.sh first." >&2
  exit 1
fi

if "$PY" -c "import pyannote.audio, torch" >/dev/null 2>&1; then
  echo "[setup-diar] pyannote already installed: $ENV_DIR" >&2
  echo "$PY"
  exit 0
fi

echo "[setup-diar] installing pyannote.audio + torch (large, one-time)…" >&2
"$PY" -m pip install -q "pyannote.audio>=3.1" torch torchaudio >&2 \
  || { echo "[setup-diar] pip install failed" >&2; exit 1; }

if "$PY" -c "import pyannote.audio, torch" >/dev/null 2>&1; then
  echo "[setup-diar] done. Next: accept model terms on huggingface.co, then run" >&2
  echo "[setup-diar] diarize_single_mic.py once with an HF token to cache the model." >&2
  echo "$PY"
else
  echo "[setup-diar] still unhealthy after install" >&2
  exit 1
fi
