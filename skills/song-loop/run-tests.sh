#!/usr/bin/env bash
# run-tests.sh — song-loop's test suite (this directory).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${CML_ENV_DIR:-$HOME/.cache/mlx-whisper-transcribe/venv}/bin/python"
if [ ! -x "$PY" ]; then
  PY="$(command -v python3)"
fi
"$PY" -m py_compile "$HERE/scripts/chords.py" "$HERE/scripts/structure.py"
bash -n "$HERE/scripts/setup_chords.sh"
"$PY" "$HERE/scripts/chords.py" --selftest
"$PY" "$HERE/scripts/structure.py" --selftest
echo "song-loop tests OK"
