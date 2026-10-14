"""`meeting-loop record [--stop]`: start and stop the Mac mic, through the real
command and the real recorder script. The microphone is the one boundary faked:
a stand-in `ffmpeg` on PATH plays the mic (lists one device, writes audio bytes
until it is told to stop), so the test runs with no hardware and no permission prompt.
"""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
CMD = SKILL / "bin" / "meeting-loop"
RESULT_PREFIX = "MEETING_LOOP_RESULT "

FAKE_FFMPEG = r"""#!/usr/bin/env bash
case " $* " in
  *" -list_devices true "*)
    echo "[AVFoundation indev @ 0x1] AVFoundation audio devices:" >&2
    echo "[AVFoundation indev @ 0x1] [0] Test Microphone" >&2
    exit 0 ;;
esac
out="${@: -1}"
trap 'exit 255' INT TERM
printf 'RIFF-fake-audio' > "$out"
while true; do printf '.' >> "$out"; sleep 0.1; done
"""


def result_of(proc):
    last = proc.stdout.rstrip("\n").splitlines()[-1]
    assert last.startswith(RESULT_PREFIX), f"last line not machine-readable: {last!r}"
    return json.loads(last[len(RESULT_PREFIX):])


class RecordTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)
        fake_bin = self.home / "fakebin"
        fake_bin.mkdir()
        (fake_bin / "ffmpeg").write_text(FAKE_FFMPEG)
        (fake_bin / "ffmpeg").chmod(0o755)
        self.env = {k: v for k, v in os.environ.items() if not k.startswith(("MEETING_LOOP", "REC_"))}
        self.env["HOME"] = str(self.home)
        self.env["PATH"] = f"{fake_bin}:{self.env['PATH']}"

    def tearDown(self):
        subprocess.run([str(CMD), "record", "--stop"], capture_output=True, env=self.env, timeout=30,
                       stdin=subprocess.DEVNULL)  # never leave a stand-in recorder running
        self._tmp.cleanup()

    def record(self, *args):
        return subprocess.run([str(CMD), "record", *args], capture_output=True, text=True, env=self.env,
                              timeout=30, stdin=subprocess.DEVNULL)

    def test_stop_with_nothing_recording_fails_plainly(self):
        proc = self.record("--stop")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("nothing is recording", proc.stderr)
        self.assertFalse(result_of(proc)["ok"])

    def test_record_reminds_about_consent_then_stop_hands_back_the_recording(self):
        start = self.record()
        self.assertEqual(start.returncode, 0, start.stderr)
        self.assertIn("being recorded", start.stdout)
        started = result_of(start)
        self.assertTrue(started["ok"])
        self.assertTrue(started["recording"])

        again = self.record()
        self.assertEqual(again.returncode, 1)
        self.assertIn("already recording", again.stderr)

        stop = self.record("--stop")
        self.assertEqual(stop.returncode, 0, stop.stderr)
        stopped = result_of(stop)
        self.assertTrue(stopped["ok"])
        [wav] = [Path(f) for f in stopped["files"]]
        self.assertEqual(str(wav), started["recording"])
        self.assertTrue(wav.is_relative_to(self.home / "MeetingLoop" / "Recordings"), wav)
        self.assertGreater(wav.stat().st_size, 0)
        self.assertIn("meeting-loop process", stop.stdout)


if __name__ == "__main__":
    unittest.main()
