# Engine upgrades — what to swap, what to keep (2026 research)

Source: deep-research pass, 2026-07-21 (Claude-side single stream — Perplexity was out of API quota that run, so treat numbers as well-sourced but un-cross-checked). Question: is there a materially better *local, offline, Apple-Silicon* stack than `whisper-large-v3-turbo` + the hand-rolled two-mic RMS diarizer?

## Bottom line
Keep the current ASR default. The real upgrade is **single-mic diarization**, which the skill has no fallback for today. Audio conversion is already handled (ffmpeg, added this pass).

## ASR — keep `whisper-large-v3-turbo` (don't swap by default)
- `mlx-community/parakeet-tdt-0.6b-v3` (`pip install parakeet-mlx`) is ~2x faster than turbo on M-series, slightly lower WER (~6.34% avg, 25 European langs), and — usefully for meetings — **doesn't hallucinate during silence**. CC-BY-4.0.
- BUT: English/European-only, memory pressure on long files (full attention ~24 min; local attention up to ~3 hr), and a younger Mac toolchain. Turbo stays the default for multilingual coverage + long-form robustness + ecosystem maturity.
- The "3000x realtime" parakeet figures are A100 batch marketing, not M-series. Independent M4 tests show ~2x over turbo — meaningful, not transformative.
- **Optional future add:** a `--engine parakeet` fast lane in `transcribe.py` for English-only, short recordings where speed matters. Not needed now.
- distil-whisper and Canary: not worth adding (distil is outclassed by parakeet; Canary has no mature MLX path).

## Diarization — single-mic fallback: BUILT (opt-in)
Shipped as `scripts/diarize_single_mic.py` + `scripts/setup_diarization.sh` (pyannote kept out of the base venv). Two-mic RMS is fine when there ARE two mics; this covers the common single-mic meeting. Detail below.

The two-mic RMS diarizer is fine when there ARE two mics; it does nothing for the common single-mic meeting. Best local option:
- **`pyannote/speaker-diarization-3.1`** (`pip install pyannote.audio`). MIT, pure PyTorch. DER ~12–22% by dataset. Gating is **one-time**: accept model terms + download once with an HF token, then it runs **fully offline from cache** — not a blocker for a privacy-first pipeline once cached.
- Apple Silicon caveat: **run it on CPU** — the MPS backend is incomplete/often slower for this pipeline. Ingests 16 kHz mono (which `transcribe.py`/ffmpeg already produce).
- NVIDIA **Sortformer** (`nvidia/diar_streaming_sortformer_4spk-v2`) roughly halves DER vs pyannote but needs the full **NeMo** framework — a heavy, CUDA-oriented, unverified install on macOS. Skip unless DER on messy multi-speaker meetings becomes the binding constraint.
- whisperx = pyannote wrapper (same gate, same CPU reality). diart = streaming, less accurate offline. Neither is a better diarizer.

**Setup (one-time):** `scripts/setup_diarization.sh`, then accept the HF terms for `pyannote/speaker-diarization-3.1` + `pyannote/segmentation-3.0` and run once with an HF token to cache. After that it's fully offline (`HF_HUB_OFFLINE=1`). Wired into SKILL.md Step 5 as the single-recorder branch; falls back to best-effort if pyannote isn't installed.

## Chords — Basic Pitch on creative tapes (2026-09-25)
Creative sessions get a second local pass: Spotify **Basic Pitch** (ONNX, same whisper venv via
`setup_chords.sh`) transcribes notes, then `chords.py` template-matches maj/min/7/sus/dim/aug.
Not a chord transformer. Wired as Step 4b; skipped on every other meeting type. Swap later only if
a dedicated ACR model (ChordMini/BTC) is worth the PyTorch weight.

## Audio — done this pass
M4A/AAC/MP4/MOV now auto-convert to 16 kHz mono WAV via a local `ffmpeg -i in -ac 1 -ar 16000 -c:a pcm_s16le out.wav` call inside `transcribe.py` (falls back to ffmpeg for anything soundfile can't read). ffmpeg is the standard; openai-whisper already shells out to it internally. `brew install ffmpeg` once; no manual conversion.

## Weak-evidence flags
- Single-stream research (no Perplexity cross-check this run).
- No clean conversational-WER comparison of parakeet-v3 vs turbo on Mac; leaderboard WER is read-speech-weighted — treat the accuracy edge as roughly a wash.
- pyannote-on-CPU-for-Mac is consistent across GitHub issues but anecdotal.
- Sortformer's "halves DER" is NVIDIA-sourced; macOS installability unverified.
