---
name: song-loop
description: >
  Turn a song Voice Memo or bounce into lyrics, chords, and a rough form map
  (intro/verse/chorus). Local mlx-whisper + Basic Pitch. Use on '/song-loop',
  'song loop', 'chart this song', 'chords and lyrics from this tape', 'what's
  the structure of this recording', 'transcribe this song', or a pointed-at
  song file. Not meeting-loop — music tapes only.
---

# Song Loop

Chart one song tape: lyrics, chords, rough form. Local, no cloud. Do not run
meeting-loop on these files.

## Do not

- Do not edit `Skills/meeting-loop/`. Reuse its transcribe script by path only.
- Do not file a chart into the wiki, a client folder, or a People note.
- Do not send email or upload anywhere. This is a working chart.
- Do not invent chords the model did not emit. `N` and `≈` stay.

## Step 1 — Take the file

One audio path. If several files, ask which one is the song. Confirm a short
title (song name or "untitled hook").

Default home: `Personal/music/<YYYY-MM-DD>_<kebab-title>/`.
Ask if it belongs on a named project instead. Do not guess a band folder.

## Step 2 — Engine

```
HERE=Skills/song-loop/scripts
PY="$(bash Skills/meeting-loop/scripts/setup_env.sh | tail -1)"
bash "$HERE/setup_chords.sh"
```

Scratch prefix: `~/.cache/song-loop/<run>/<stem>`.

## Step 3 — Lyrics, chords, form

```
"$PY" Skills/meeting-loop/scripts/transcribe.py "<audio>" "<prefix>"
"$PY" "$HERE/chords.py" "<audio>" "<prefix>"
"$PY" "$HERE/structure.py" "<prefix>" --title "<title>"
```

If chords setup fails, still write lyrics + structure and say the chord pass
did not run. If Whisper returns empty, still write chords.

## Step 4 — Place

Copy into the home folder (never overwrite):

- `chart.md` — the one-pager
- `lyrics.md` · `chords.md` · `structure.md`
- `raw/` — `*.json` plus a pointer to the source audio path

Frontmatter on `chart.md`: `title`, `type: note`, `created`, `source: song-loop`,
`tags: [music, songwriting]`. Open with `**What this is:**` one sentence.

Add a one-line backlink under `## Tape charts` in `Personal/music/_MOC.md` (create it if missing).

Do not git-commit.

## Step 5 — Read it back

Paste the form line, key guess, compact chord string, and the first four lyric
lines. Flag anything `≈`.
Stop.

## Output

Done when `chart.md` is on disk, the MOC has the link, and the owner has seen the
form + chords + opening lyrics in chat. Ready for a file whenever he drops one.
