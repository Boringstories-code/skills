"""Seam 1: the `meeting-loop` command, driven the way a user or agent drives it.

Each test runs the real command in a subprocess with HOME pointed at a throwaway
folder, so the default Brain lands there. Assertions are on what a user sees:
files in the Brain, exit codes, and the final machine-readable line.
"""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
CMD = SKILL / "bin" / "meeting-loop"
FIXTURE = SKILL / "tests" / "fixtures" / "sample-sitting.segments.txt"
AGENT_ITEMS = SKILL / "tests" / "fixtures" / "agent-items.json"
AGENT_HANDOFF = SKILL / "tests" / "fixtures" / "agent-handoff.json"
RESULT_PREFIX = "MEETING_LOOP_RESULT "


def run(home, *args, **extra_env):
    env = {k: v for k, v in os.environ.items() if not k.startswith("MEETING_LOOP")}
    env["HOME"] = str(home)
    env.update(extra_env)
    return subprocess.run([str(CMD), *args], capture_output=True, text=True, env=env, timeout=60,
                          stdin=subprocess.DEVNULL)  # no terminal: questions get EOF, never block


def result_of(proc):
    last = proc.stdout.rstrip("\n").splitlines()[-1]
    assert last.startswith(RESULT_PREFIX), f"last line not machine-readable: {last!r}"
    return json.loads(last[len(RESULT_PREFIX):])


def snapshot(root):
    return {p.relative_to(root): p.read_bytes() for p in Path(root).rglob("*") if p.is_file()}


class ProcessTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)
        self.brain = self.home / "MeetingLoop" / "Brain"

    def tearDown(self):
        for p in self.home.rglob("*"):  # undo any chmod a test made, so cleanup works
            if p.is_dir():
                p.chmod(0o755)
        self._tmp.cleanup()

    def test_transcript_with_llm_none_writes_transcript_and_action_items_view_into_brain(self):
        proc = run(self.home, "process", str(FIXTURE), "--llm", "none")
        self.assertEqual(proc.returncode, 0, proc.stderr)

        files = [Path(f) for f in result_of(proc)["files"]]
        self.assertTrue(files)
        for f in files:
            self.assertTrue(f.is_file(), f)
            self.assertTrue(f.is_relative_to(self.brain), f)

        transcript = next(f for f in files if f.name.startswith("transcript"))
        self.assertIn("I'll send you the photo folder by Friday.", transcript.read_text())

        view = next(f for f in files if f.suffix == ".html")
        html = view.read_text()
        self.assertIn("<html", html)
        self.assertIn("I'll send you the photo folder by Friday.", html)

    def test_second_run_into_same_brain_only_adds(self):
        first = result_of(run(self.home, "process", str(FIXTURE), "--llm", "none"))["files"]
        before = snapshot(self.brain)

        proc = run(self.home, "process", str(FIXTURE), "--llm", "none")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        second = result_of(proc)["files"]

        after = snapshot(self.brain)
        for rel, old in before.items():
            self.assertTrue(after[rel].startswith(old), f"{rel} was rewritten, not appended to")
        grew = [rel for rel in before if after[rel] != before[rel]]
        self.assertTrue(grew, "second run added nothing to existing notes")
        new_files = set(after) - set(before)
        self.assertTrue(new_files, "second run's action-items view should land beside the first")
        self.assertEqual(len(second), len(first))
        for f in second:
            self.assertTrue(Path(f).is_file(), f)

    def test_failed_write_leaves_brain_unchanged_and_says_why(self):
        first = result_of(run(self.home, "process", str(FIXTURE), "--llm", "none"))["files"]
        Path(first[0]).parent.chmod(0o555)  # the sitting's folder can no longer be written
        before = snapshot(self.brain)

        proc = run(self.home, "process", str(FIXTURE), "--llm", "none")

        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(snapshot(self.brain), before)
        self.assertIn("could not write to the Brain", proc.stderr)
        result = result_of(proc)
        self.assertFalse(result["ok"])
        self.assertEqual(result["files"], [])

    def test_local_model_without_its_engine_stops_with_plain_reason_and_writes_nothing(self):
        proc = run(self.home, "process", str(FIXTURE), "--llm", "local",
                   CML_ENV_DIR=str(self.home / "no-engine-here"))
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("isn't set up", proc.stderr)
        self.assertFalse(result_of(proc)["ok"])
        self.assertFalse(self.brain.exists())

    def test_8gb_default_skips_cleanup_offers_it_with_a_time_and_never_asks_without_a_terminal(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith("MEETING_LOOP")}
        env.update(HOME=str(self.home), MEETING_LOOP_RAM_GB="8")
        proc = subprocess.run([str(CMD), "process", str(FIXTURE), "--llm", "none", "--type", "work", "--no-entity"],
                              capture_output=True, text=True, env=env, timeout=60,
                              input="y\n")  # piped, not a terminal: a "yes" here must not be read as an answer
        self.assertEqual(proc.returncode, 0, proc.stderr)
        offer = next(l for l in proc.stdout.splitlines() if l.startswith("[clean]"))
        self.assertIn("--clean", offer)
        self.assertRegex(offer, r"about \d+(m \d\ds|s)")
        self.assertNotIn("[y/N]", proc.stdout)
        result = result_of(proc)
        self.assertEqual(result["cleanup"], {"ran": False})
        names = [Path(f).name for f in result["files"]]
        self.assertIn("transcript.md", names)
        self.assertNotIn("transcript-clean.md", names)

    def test_8gb_run_at_a_terminal_asks_with_the_extra_time_and_takes_the_answer(self):
        import pty
        env = {k: v for k, v in os.environ.items() if not k.startswith("MEETING_LOOP")}
        env.update(HOME=str(self.home), MEETING_LOOP_RAM_GB="8", CML_ENV_DIR=str(self.home / "no-engine-here"))
        run(self.home, "setup", "--yes")  # else first-run setup asks its three questions at this terminal first
        for answer in ("n", "y"):
            master, slave = pty.openpty()  # stdin is a terminal; the answer is typed into it up front
            os.write(master, f"{answer}\n".encode())
            proc = subprocess.run([str(CMD), "process", str(FIXTURE), "--llm", "none", "--type", "work", "--no-entity"],
                                  stdin=slave, capture_output=True, text=True, env=env, timeout=60)
            os.close(slave)
            os.close(master)
            self.assertRegex(proc.stdout, r"\[clean\] clean up the transcript wording too\? It adds about \d+.*\[y/N\]")
            if answer == "n":
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertEqual(result_of(proc)["cleanup"], {"ran": False})
            else:  # "yes" reaches for the model, which this home doesn't have
                self.assertNotEqual(proc.returncode, 0)
                self.assertIn("isn't set up", proc.stderr)

    def test_clean_without_the_model_engine_stops_with_plain_reason_and_writes_nothing(self):
        proc = run(self.home, "process", str(FIXTURE), "--llm", "none", "--clean",
                   CML_ENV_DIR=str(self.home / "no-engine-here"))
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("isn't set up", proc.stderr)
        self.assertFalse(result_of(proc)["ok"])
        self.assertFalse(self.brain.exists())

    def test_no_clean_and_llm_none_never_load_a_model(self):
        for args in (["--no-clean"], []):
            proc = run(self.home, "process", str(FIXTURE), "--llm", "none", *args,
                       CML_ENV_DIR=str(self.home / "no-engine-here"))  # any model load would fail the run
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(result_of(proc)["cleanup"], {"ran": False})

    def test_quote_check_drops_a_planted_fake_item_and_reports_kept_and_dropped(self):
        # Agent handoff is the test-only route to the quote check / owner rule: it is
        # the same function the local keyword matcher runs its own items through.
        proc = run(self.home, "process", str(FIXTURE), "--llm", "agent", "--agent-items", str(AGENT_ITEMS))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = result_of(proc)
        self.assertTrue(result["ok"])
        # agent-items.json plants 4 candidates: one with a fake quote (dropped) and
        # three with real quotes from the fixture transcript (kept).
        self.assertEqual(result["action_items"], {"kept": 3, "dropped": 1})

        notes = next(Path(f) for f in result["files"] if Path(f).name.startswith("notes"))
        text = notes.read_text()
        # the fake item never appears anywhere in the Brain
        self.assertNotIn("fly to the moon", text)
        # a real item with a matching quote survives, case-insensitively
        self.assertIn("Send photo folder", text)

    def test_owner_named_only_when_the_quoted_line_or_a_neighbor_names_one(self):
        proc = run(self.home, "process", str(FIXTURE), "--llm", "agent", "--agent-items", str(AGENT_ITEMS))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        notes = next(Path(f) for f in result_of(proc)["files"] if Path(f).name.startswith("notes")).read_text()

        # "I'll send you..." names its own speaker.
        self.assertIn("Send photo folder (owner: Host)", notes)
        # "Can you also check..." has no stated owner itself, but the next line
        # ("Yes, I will call the venue...") answers it in the first person.
        self.assertIn("Check event dates (owner: Host)", notes)
        # "Then we need to pick a headline..." names no one, and neither neighbor
        # answers it in the first person -- unassigned.
        self.assertIn("Pick a headline (owner: unassigned)", notes)

    def test_agent_handoff_carries_the_agents_summary_and_still_quote_checks_its_items(self):
        # The skill pack's handoff shape: {"summary", "action_items"}.
        proc = run(self.home, "process", str(FIXTURE), "--no-entity", "--type", "work",
                   "--llm", "agent", "--agent-items", str(AGENT_HANDOFF))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(result_of(proc)["action_items"], {"kept": 1, "dropped": 1})
        notes = next(Path(f) for f in result_of(proc)["files"] if Path(f).name == "notes.md").read_text()
        self.assertIn("photos are the holdup", notes)
        self.assertIn("Send photo folder", notes)
        self.assertNotIn("rocket", notes)

    def test_sitting_flag_quote_checks_items_against_every_recording_in_the_sitting(self):
        # The fixture split in two files of one sitting: items quote lines from both halves.
        lines = FIXTURE.read_text().splitlines()
        part1, part2 = self.home / "part1.segments.txt", self.home / "part2.segments.txt"
        part1.write_text("\n".join(lines[:4]) + "\n")
        part2.write_text("\n".join(lines[4:]) + "\n")
        proc = run(self.home, "process", str(part1), str(part2), "--sitting",
                   "--llm", "agent", "--agent-items", str(AGENT_ITEMS))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = result_of(proc)
        self.assertEqual(result["action_items"], {"kept": 3, "dropped": 1})
        self.assertEqual(len([f for f in result["files"] if Path(f).name == "notes.md"]), 1)

    def test_entity_note_goes_to_the_profiles_entity_notes_folder(self):
        run(self.home, "setup", "--yes")
        profile = self.home / ".meeting-loop" / "profile.json"
        data = json.loads(profile.read_text())
        data["brain"]["folder_map"] = {"entity_notes": "Clients/"}
        profile.write_text(json.dumps(data))
        proc = run(self.home, "process", str(FIXTURE), "--llm", "none", "--entity", "Acme Co")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue((self.brain / "Clients" / "acme-co.md").is_file(), result_of(proc)["files"])


NO_LABELS = "No speaker labels"
ENGINE_PY = Path(os.environ.get("CML_ENV_DIR", Path.home() / ".cache/mlx-whisper-transcribe/venv")) / "bin" / "python"
HF_HOME = Path(os.environ.get("HF_HOME", Path.home() / ".cache/huggingface"))
WHISPER_CACHED = any((HF_HOME / "hub" / "models--mlx-community--whisper-large-v3-turbo" / "snapshots").glob("*/config.json"))


class SpeakerLabelsTest(unittest.TestCase):
    """Story 45: two mics give speaker labels; one mic says plainly there are none."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def process(self, *recordings, **env):
        proc = run(self.home, "process", *map(str, recordings), "--llm", "none", "--no-clean",
                   "--type", "work", "--no-entity", **env)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        transcripts = [Path(f) for f in result_of(proc)["files"] if Path(f).name == "transcript.md"]
        self.assertEqual(len(transcripts), 1)
        return proc, transcripts[0].read_text()

    def speakerless(self):
        path = self.home / "speakerless.segments.txt"
        path.write_text("".join(l.split("] ", 1)[0] + "] " + l.split(": ", 1)[1] + "\n"
                                for l in FIXTURE.read_text().splitlines()))
        return path

    def test_one_mic_transcript_without_speakers_says_plainly_it_has_none(self):
        run(self.home, "setup", "--yes")
        _, text = self.process(self.speakerless())
        self.assertIn("No speaker labels: recorded with one mic.", text.splitlines()[:3])

    def test_transcript_that_already_names_its_speakers_gets_no_no_labels_line(self):
        run(self.home, "setup", "--yes")
        _, text = self.process(FIXTURE)
        self.assertNotIn(NO_LABELS, text)
        self.assertIn("Host: I'll send you the photo folder by Friday.", text)

    def test_two_mic_profile_but_not_two_audio_recordings_falls_through_and_says_why(self):
        run(self.home, "setup", "--yes", "--mics", "two")
        proc, text = self.process(self.speakerless())
        why = [l for l in proc.stdout.splitlines() if NO_LABELS in l]
        self.assertEqual(len(why), 1, proc.stdout)
        self.assertIn("two mics", why[0])
        self.assertIn(NO_LABELS, "\n".join(text.splitlines()[:3]))

    @unittest.skipUnless(ENGINE_PY.is_file() and WHISPER_CACHED and shutil.which("ffmpeg") and shutil.which("say"),
                         "needs the engine venv, the cached Whisper model, ffmpeg and macOS say")
    def test_two_mic_sitting_transcribes_the_spine_once_and_labels_each_line(self):
        # Two people, one mic each: each mic hears its wearer loud and the other at -6 dB.
        said = {"a": "Thanks for coming in today. Let's talk about the spring newsletter.",
                "b": "Sure. I will send you the photo folder by Friday."}
        for k in said:  # one voice is enough: the labels come from which mic is louder, not the voice
            subprocess.run(["say", "-o", str(self.home / f"{k}.aiff"), said[k]], check=True)
        mics = [self.home / "MIC1.wav", self.home / "MIC2.wav"]
        for out, (va, vb) in zip(mics, (("1", "0.5"), ("0.5", "1"))):
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(self.home / "a.aiff"),
                            "-i", str(self.home / "b.aiff"), "-filter_complex",
                            f"[0]volume={va},apad=pad_dur=1[a];[1]volume={vb}[b];[a][b]concat=n=2:v=0:a=1[o]",
                            "-map", "[o]", "-ar", "16000", "-ac", "1", str(out)], check=True)
        os.utime(mics[1], (mics[0].stat().st_mtime + 1,) * 2)  # MIC1 is the spine: first by mtime
        run(self.home, "setup", "--yes", "--mics", "two")

        proc, text = self.process(*mics, "--sitting", CML_ENV_DIR=str(ENGINE_PY.parent.parent),
                                  HF_HOME=str(HF_HOME))
        self.assertNotIn(NO_LABELS, text)
        self.assertEqual(text.count("## "), 1, "the two mics are one transcript, not two")
        labelled = [l for l in text.splitlines() if l.startswith("[")]
        self.assertRegex(labelled[0], r"\] Speaker 1: .*spring newsletter")  # Whisper's punctuation varies
        self.assertRegex(labelled[-1], r"\] Speaker 2: .*photo folder")


if __name__ == "__main__":
    unittest.main()
