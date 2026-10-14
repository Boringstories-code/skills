#!/usr/bin/env bash
# run-tests.sh — Meeting Loop's whole local suite in one command. No models, no network.
#   1. the `meeting-loop` command against the recorded-transcript fixture (tests/)
#   2. scripts/ seam tests that live beside the script they cover (not under tests/,
#      which unittest discover never walks into scripts/) — vault-specific, so the
#      public release tree (release.json's allowlist) never ships them; skipped with
#      a printed line when absent, same pattern as the engine selftest below
#   3. the engine selftest, fast mode (skipped with a printed line when the engine
#      venv was never set up, since building it downloads packages)
set -uo pipefail
cd "$(dirname "$0")"
rc=0

echo "== meeting-loop command =="
python3 -m unittest discover -s tests || rc=1

echo "== scripts/ seam tests =="
if [ -f scripts/test_draft_quote_request.py ]; then
  python3 -m unittest scripts.test_draft_quote_request -v || rc=1
else
  echo "SKIP scripts/ seam tests: test_draft_quote_request.py not staged here"
fi

echo "== engine selftest (fast) =="
if [ -x "${CML_ENV_DIR:-$HOME/.cache/mlx-whisper-transcribe/venv}/bin/python" ]; then
  bash scripts/selftest.sh || rc=1
else
  echo "SKIP engine selftest: venv not set up (run: bash scripts/setup_env.sh)"
fi

[ "$rc" -eq 0 ] && echo "run-tests: PASS" || echo "run-tests: FAIL"
exit "$rc"
