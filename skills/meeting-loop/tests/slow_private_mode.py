"""Opt-in, slow: Private mode with the real on-device model, network denied.

    python3 tests/slow_private_mode.py        (not part of run-tests.sh: it needs the
                                              engine venv and both Qwen3 models cached)

Runs the real `meeting-loop process --llm local` under `sandbox-exec` with all network
denied, in a throwaway HOME (the model cache and engine venv are passed in), and checks:
  1. the sample sitting gets a summary and quote-checked action items, no 8 GB note;
  2. the 8 GB path (MEETING_LOOP_RAM_GB=8) puts the note in stdout, notes, HTML and result;
  3. a long transcript is read in several parts with progress and a time estimate;
  4. cleanup (ticket 04): on by default on 16 GB+, skipped with a time offer on 8 GB,
     opt-in there with --clean; every timestamp and speaker label survives it.
Prints each run's output and timing so the numbers can be recorded.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))
import meeting_loop  # noqa: E402
CMD = SKILL / "bin" / "meeting-loop"
FIXTURE = SKILL / "tests" / "fixtures" / "sample-sitting.segments.txt"
NO_NETWORK = "(version 1)(allow default)(deny network*)"
REAL_HOME = Path.home()


def run(home, transcript, *flags, **extra_env):
    env = {k: v for k, v in os.environ.items() if not k.startswith("MEETING_LOOP")}
    env.update(HOME=str(home), HF_HOME=os.environ.get("HF_HOME", str(REAL_HOME / ".cache/huggingface")),
               CML_ENV_DIR=os.environ.get("CML_ENV_DIR", str(REAL_HOME / ".cache/mlx-whisper-transcribe/venv")),
               **extra_env)
    t = time.time()
    proc = subprocess.run(["sandbox-exec", "-p", NO_NETWORK, str(CMD), "process", str(transcript),
                           "--llm", "local", "--type", "work", "--no-entity", *flags],
                          capture_output=True, text=True, env=env, stdin=subprocess.DEVNULL, timeout=1800)
    print(f"\n--- {transcript.name} {' '.join(flags)} {extra_env or ''} ({time.time() - t:.0f}s wall) ---\n"
          f"{proc.stdout}{proc.stderr}")
    return proc


def long_transcript(path, repeats):
    """The sample sitting said `repeats` times in a row, timestamps running on (a real
    transcript never repeats a timestamp)."""
    def later(off):
        def shift(m):
            h, mi, s = m[1].split(":")
            t = int(h) * 3600 + int(mi) * 60 + float(s) + off
            return f"{int(t // 3600):02d}:{int(t % 3600 // 60):02d}:{t % 60:06.3f}"
        return shift
    lines = FIXTURE.read_text().splitlines()
    path.write_text("\n".join(re.sub(r"(\d\d:\d\d:\d\d\.\d{3})", later(34 * r), l)
                              for r in range(repeats) for l in lines) + "\n")
    return path


def part_secs(stdout, tag):
    """Seconds each '[tag] part n/N done in 1m 05s' line reports, summed."""
    return sum(int(m or 0) * 60 + int(s) for m, s in
               re.findall(rf"\[{tag}\] part \d+/\d+ done in (?:(\d+)m )?(\d+)s", stdout))


def result_of(proc):
    return json.loads(proc.stdout.rstrip("\n").splitlines()[-1].split(" ", 1)[1])


def read(result, suffix):
    return next(Path(f) for f in result["files"] if f.endswith(suffix)).read_text()


class PrivateModeRealModel(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_sample_sitting_gets_summary_and_quote_checked_items_with_network_off(self):
        proc = run(self.home, FIXTURE)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = result_of(proc)
        self.assertGreaterEqual(result["action_items"]["kept"], 2)
        notes = read(result, "notes.md")
        print(notes)
        self.assertNotIn("none (--llm none", notes)
        self.assertIn("photo folder", notes)
        if local_ram_gb() >= 16:
            self.assertNotIn("note", result)
            self.assertNotIn("less refined", notes)

    def test_8gb_path_says_results_are_simpler_everywhere(self):
        proc = run(self.home, FIXTURE, MEETING_LOOP_RAM_GB="8")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("Qwen3-4B", proc.stdout)
        result = result_of(proc)
        for where in (proc.stdout, result["note"], read(result, "notes.md"), read(result, ".html")):
            self.assertIn("simpler and less refined on this Mac", where)

    def assert_clean_keeps_every_label(self, result):
        raw = meeting_loop.load_transcript_text(read(result, "/transcript.md"))
        clean = meeting_loop.load_transcript_text(read(result, "/transcript-clean.md"))
        print(read(result, "/transcript-clean.md")[:3000])
        self.assertEqual([(l["ts"], l["speaker"]) for l in clean], [(l["ts"], l["speaker"]) for l in raw])
        self.assertTrue(result["cleanup"]["ran"])
        print("fallbacks:", result["cleanup"]["fallbacks"], "of", result["cleanup"]["lines"])

    def test_16gb_default_cleans_the_wording_and_keeps_every_label_and_the_raw_transcript(self):
        if local_ram_gb() < 16:
            self.skipTest("needs a 16 GB+ Mac")
        messy = self.home / "messy-sitting.segments.txt"  # filler the cleanup should take out
        messy.write_text(FIXTURE.read_text().replace("Host: ", "Host: Um, so, uh, ").replace(
            "Guest: ", "Guest: Yeah, you know, I I think "))
        proc = run(self.home, messy)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = result_of(proc)
        for line in messy.read_text().splitlines():
            self.assertIn(line, read(result, "/transcript.md"))  # raw kept exactly as heard
        self.assert_clean_keeps_every_label(result)
        self.assertLess(read(result, "/transcript-clean.md").count("uh,"), messy.read_text().count("uh,"))

    def test_8gb_default_skips_cleanup_and_offers_it_with_the_extra_time(self):
        proc = run(self.home, FIXTURE, MEETING_LOOP_RAM_GB="8")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertRegex(proc.stdout, r"\[clean\] skipped .* about \d+")
        self.assertFalse(any(f.endswith("transcript-clean.md") for f in result_of(proc)["files"]))

    def assert_cleanup_in_parts(self, proc, long, label):
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("[clean] part 1/3 done", proc.stdout)
        self.assert_clean_keeps_every_label(result_of(proc))
        kchars = len(long.read_text()) / 1000
        print(f"cleanup speed ({label}): {part_secs(proc.stdout, 'clean') / kchars:.1f} s per 1000 chars")

    def test_8gb_with_clean_runs_cleanup_on_the_small_model_in_parts(self):
        long = long_transcript(self.home / "long-sitting.segments.txt", 12)  # ~8k chars: three cleanup parts
        proc = run(self.home, long, "--clean", MEETING_LOOP_RAM_GB="8")
        self.assertIn("Qwen3-4B", proc.stdout)
        self.assert_cleanup_in_parts(proc, long, "Qwen3-4B")

    def test_16gb_cleanup_of_a_longer_transcript_runs_in_parts_with_a_time_estimate(self):
        if local_ram_gb() < 16:
            self.skipTest("needs a 16 GB+ Mac")
        long = long_transcript(self.home / "long-sitting.segments.txt", 12)
        proc = run(self.home, long)
        self.assertIn("left", proc.stdout)
        self.assert_cleanup_in_parts(proc, long, "Qwen3-8B")

    def test_long_transcript_is_read_in_parts_with_a_time_estimate(self):
        long = long_transcript(self.home / "long-sitting.segments.txt", 40)  # ~20k chars: three parts
        proc = run(self.home, long, "--no-clean")  # cleanup speed is measured above; this one is synthesis
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("part 1/3 done", proc.stdout)
        self.assertIn("left", proc.stdout)
        self.assertIn("combining 3 part summaries", proc.stdout)

def local_ram_gb():
    return int(subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True).stdout) / 2 ** 30


if __name__ == "__main__":
    unittest.main(argv=sys.argv[:1] + sys.argv[1:], verbosity=2)
