"""Seam 1 (continued): the small single-purpose subcommands behind the MCP
server's tools -- find, transcribe, render, write, version. Same house style
as test_process.py: drive the real `bin/meeting-loop` in a subprocess with a
throwaway HOME, assert on files/exit codes/the final machine-readable line.
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
RENDER_FIXTURE = SKILL / "tests" / "fixtures" / "render-items.json"
RESULT_PREFIX = "MEETING_LOOP_RESULT "


def run(home, *args):
    env = {k: v for k, v in os.environ.items() if not k.startswith("MEETING_LOOP")}
    env["HOME"] = str(home)
    return subprocess.run([str(CMD), *args], capture_output=True, text=True, env=env, timeout=60,
                          stdin=subprocess.DEVNULL)


def result_of(proc):
    last = proc.stdout.rstrip("\n").splitlines()[-1]
    assert last.startswith(RESULT_PREFIX), f"last line not machine-readable: {last!r}"
    return json.loads(last[len(RESULT_PREFIX):])


class VersionTest(unittest.TestCase):
    def test_version_prints_the_installed_version_and_a_result_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = run(tmp, "version")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = result_of(proc)
        self.assertTrue(result["ok"])
        self.assertEqual(result["version"], (SKILL / "VERSION").read_text().strip())


class FindTest(unittest.TestCase):
    def test_find_proposes_one_group_for_recordings_close_together(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            recs = home / "recs"
            recs.mkdir()
            shutil.copy(FIXTURE, recs / "a.txt")
            shutil.copy(FIXTURE, recs / "b.txt")
            proc = run(home, "find", str(recs))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = result_of(proc)
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["groups"]), 1)
        self.assertEqual(len(result["groups"][0]), 2)

    def test_find_fails_plainly_on_an_empty_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            empty = home / "empty"
            empty.mkdir()
            proc = run(home, "find", str(empty))
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("no recordings found", proc.stderr)


class RenderTest(unittest.TestCase):
    def test_render_writes_html_beside_the_items_file_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            items = home / "items.json"
            items.write_text(RENDER_FIXTURE.read_text())
            proc = run(home, "render", str(items))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            result = result_of(proc)
            self.assertTrue(result["ok"])
            out = Path(result["files"][0])
            self.assertEqual(out, items.with_suffix(".html"))
            html = out.read_text()
            self.assertIn("<html", html)
            self.assertIn("Send photo folder", html)

    def test_render_honors_out(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            items = home / "items.json"
            items.write_text(RENDER_FIXTURE.read_text())
            out = home / "elsewhere" / "view.html"
            proc = run(home, "render", str(items), "--out", str(out))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue(out.is_file())

    def test_render_fails_plainly_on_bad_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            items = home / "items.json"
            items.write_text("not json")
            proc = run(home, "render", str(items))
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("couldn't read", proc.stderr)


class WriteTest(unittest.TestCase):
    def test_write_appends_a_dated_block_and_a_second_call_only_appends(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            first = run(home, "write", "Entities/acme.md", "--text", "first entry")
            self.assertEqual(first.returncode, 0, first.stderr)
            note = Path(result_of(first)["files"][0])
            before = note.read_text()
            self.assertIn("first entry", before)

            second = run(home, "write", "Entities/acme.md", "--text", "second entry")
            self.assertEqual(second.returncode, 0, second.stderr)
            after = note.read_text()
            self.assertTrue(after.startswith(before), "second write did not append, it rewrote")
            self.assertIn("first entry", after)
            self.assertIn("second entry", after)

    def test_write_from_a_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            src = home / "body.txt"
            src.write_text("from a file\n")
            proc = run(home, "write", "Entities/acme.md", "--file", str(src))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            note = Path(result_of(proc)["files"][0])
            self.assertIn("from a file", note.read_text())

    def test_write_refuses_a_note_path_outside_the_brain(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            outside = home / "outside.md"
            for note in ["../../../../outside.md", str(outside)]:
                proc = run(home, "write", note, "--text", "escaped")
                self.assertNotEqual(proc.returncode, 0, note)
                self.assertIn("outside the Brain", proc.stdout + proc.stderr)
            self.assertFalse(outside.exists())
            self.assertEqual(list(home.rglob("outside*.md")), [])

    def test_write_requires_text_or_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = run(tmp, "write", "Entities/acme.md")
        self.assertNotEqual(proc.returncode, 0)


if __name__ == "__main__":
    unittest.main()
