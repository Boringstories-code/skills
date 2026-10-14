"""Ticket 05: ask, don't assume — grouping, meeting type, entity note.

Same house as test_process.py: drive the real `meeting-loop` command in a
subprocess, HOME pointed at a throwaway folder. Interactive prompts are
answered by piping `input=` to stdin; "no terminal" is simulated by piping
nothing (stdin is open but gives EOF immediately), never by faking isatty.
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
RESULT_PREFIX = "MEETING_LOOP_RESULT "


def run(home, *args, stdin_text=""):
    env = {k: v for k, v in os.environ.items() if not k.startswith("MEETING_LOOP")}
    env["HOME"] = str(home)
    return subprocess.run([str(CMD), *args], capture_output=True, text=True, env=env,
                           input=stdin_text, timeout=60)


def result_of(proc):
    last = proc.stdout.rstrip("\n").splitlines()[-1]
    assert last.startswith(RESULT_PREFIX), f"last line not machine-readable: {last!r}"
    return json.loads(last[len(RESULT_PREFIX):])


def snapshot(root):
    return {p.relative_to(root): p.read_bytes() for p in Path(root).rglob("*") if p.is_file()}


def recording(home, name, mtime_offset_s):
    """A copy of the fixture under a new name, mtime shifted by mtime_offset_s
    seconds from the fixture's own mtime (so grouping has something to key off)."""
    dest = home / name
    shutil.copyfile(FIXTURE, dest)
    base = FIXTURE.stat().st_mtime
    t = base + mtime_offset_s
    os.utime(dest, (t, t))
    return dest


class GroupingTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)
        self.brain = self.home / "MeetingLoop" / "Brain"

    def tearDown(self):
        for p in self.home.rglob("*"):
            if p.is_dir():
                p.chmod(0o755)
        self._tmp.cleanup()

    def test_close_recordings_propose_grouping_and_merge_on_yes(self):
        a = recording(self.home, "a.segments.txt", 0)
        b = recording(self.home, "b.segments.txt", 300)  # 5 min later: same sitting

        proc = run(self.home, "process", str(a), str(b), "--type", "work", "--no-entity", "--llm", "none",
                   stdin_text="yes\n")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("proposed sitting groups", proc.stdout)

        files = [Path(f) for f in result_of(proc)["files"]]
        sittings = {f.parent for f in files}
        self.assertEqual(len(sittings), 1, f"expected one merged sitting, got {sittings}")

        transcript = next(f for f in files if f.name.startswith("transcript")).read_text()
        self.assertIn("a.segments.txt", transcript)
        self.assertIn("b.segments.txt", transcript)

    def test_close_recordings_with_no_answer_process_separately(self):
        a = recording(self.home, "a.segments.txt", 0)
        b = recording(self.home, "b.segments.txt", 300)

        proc = run(self.home, "process", str(a), str(b), "--type", "work", "--no-entity", "--llm", "none",
                   stdin_text="")  # no terminal, no answer
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("processing each recording as its own sitting", proc.stdout)

        files = [Path(f) for f in result_of(proc)["files"]]
        sittings = {f.parent for f in files}
        self.assertEqual(len(sittings), 2, f"expected two separate sittings, got {sittings}")

    def test_far_apart_recordings_need_no_confirmation(self):
        a = recording(self.home, "a.segments.txt", 0)
        b = recording(self.home, "b.segments.txt", 3600 * 5)  # 5 hours later: clearly separate

        proc = run(self.home, "process", str(a), str(b), "--type", "work", "--no-entity", "--llm", "none",
                   stdin_text="")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("proposed sitting groups", proc.stdout)

        files = [Path(f) for f in result_of(proc)["files"]]
        sittings = {f.parent for f in files}
        self.assertEqual(len(sittings), 2)


class TypeTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_flag_answers_the_type_question(self):
        proc = run(self.home, "process", str(FIXTURE), "--type", "client", "--no-entity", "--llm", "none")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        files = result_of(proc)["files"]
        notes = next(f for f in files if f.endswith("notes.md"))
        self.assertIn("**Type:** client", Path(notes).read_text())

    def test_unknown_type_flag_is_rejected_plainly(self):
        proc = run(self.home, "process", str(FIXTURE), "--type", "nonsense", "--no-entity", "--llm", "none")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("unknown meeting type", proc.stderr)

    def test_interactive_answer_confirms_the_type(self):
        proc = run(self.home, "process", str(FIXTURE), "--no-entity", "--llm", "none", stdin_text="personal\n")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        files = result_of(proc)["files"]
        notes = next(f for f in files if f.endswith("notes.md"))
        self.assertIn("**Type:** personal", Path(notes).read_text())

    def test_no_terminal_and_no_flag_defaults_to_work_and_says_so(self):
        proc = run(self.home, "process", str(FIXTURE), "--no-entity", "--llm", "none", stdin_text="")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("defaulting to 'work'", proc.stdout)
        files = result_of(proc)["files"]
        notes = next(f for f in files if f.endswith("notes.md"))
        self.assertIn("**Type:** work", Path(notes).read_text())


class EntityNoteTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)
        self.brain = self.home / "MeetingLoop" / "Brain"

    def tearDown(self):
        for p in self.home.rglob("*"):
            if p.is_dir():
                p.chmod(0o755)
        self._tmp.cleanup()

    def test_named_entity_gets_a_dated_entry_without_touching_existing_content(self):
        entity_path = self.brain / "Entities" / "acme.md"
        entity_path.parent.mkdir(parents=True)
        entity_path.write_text("# Acme\n\nPre-existing client history. Do not touch.\n")
        before = entity_path.read_bytes()

        proc = run(self.home, "process", str(FIXTURE), "--type", "client", "--entity", "Acme", "--llm", "none")
        self.assertEqual(proc.returncode, 0, proc.stderr)

        after = entity_path.read_bytes()
        self.assertTrue(after.startswith(before), "existing entity content was altered")
        self.assertGreater(len(after), len(before), "no dated entry was appended")
        self.assertIn(b"Type: client", after)

    def test_no_entity_flag_skips_and_says_so(self):
        proc = run(self.home, "process", str(FIXTURE), "--type", "work", "--no-entity", "--llm", "none")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("skipping the entity note", proc.stdout)
        self.assertFalse((self.brain / "Entities").exists())

    def test_non_interactive_without_entity_flag_writes_no_note_and_says_so(self):
        proc = run(self.home, "process", str(FIXTURE), "--type", "work", "--llm", "none", stdin_text="")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("no entity note named; skipping", proc.stdout)
        self.assertFalse((self.brain / "Entities").exists())
        files = result_of(proc)["files"]
        self.assertFalse(any("Entities" in f for f in files))

    def test_interactive_answer_names_the_entity(self):
        proc = run(self.home, "process", str(FIXTURE), "--type", "work", "--llm", "none", stdin_text="Acme\n")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue((self.brain / "Entities" / "acme.md").is_file())

    def test_failed_entity_write_rolls_back_the_whole_sitting(self):
        first = run(self.home, "process", str(FIXTURE), "--type", "client", "--entity", "Acme", "--llm", "none")
        self.assertEqual(first.returncode, 0, first.stderr)
        before = snapshot(self.brain)

        (self.brain / "Entities").chmod(0o555)  # entity folder can no longer be written

        proc = run(self.home, "process", str(FIXTURE), "--type", "client", "--entity", "Acme", "--llm", "none")

        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("could not write to the Brain", proc.stderr)
        self.assertEqual(snapshot(self.brain), before, "a partial write leaked into the Brain")
        result = result_of(proc)
        self.assertFalse(result["ok"])
        self.assertEqual(result["files"], [])


if __name__ == "__main__":
    unittest.main()
