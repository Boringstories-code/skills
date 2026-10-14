# Capturing audio (optional front-end)

`recorder/record.sh <client-slug> [topic]` records the Mac mic straight to a 16 kHz mono WAV (the
exact format this engine wants) in `~/MeetingRecordings/`, auto-picking the real mic (skips BlackHole
and other virtual inputs) and printing the file path on the last line. Press `q` then Enter to stop.

- Filename convention `<slug>__<topic>__<timestamp>.wav` carries the client hint.
- No launchd, no daemon — you run it, then say "run the meeting-loop on <that path>".
- For phone capture, record in Voice Memos and AirDrop the file over.
- `record.sh --list` shows mics; `REC_DIR`/`REC_MIC` override defaults.
