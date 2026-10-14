"""Ticket 11's comparison tool, with a stand-in model (no MLX): catch rate, invented
count and the PASS line come out right for the sample sitting."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))
import quality_bar  # noqa: E402

FIXTURE = SKILL / "tests" / "fixtures" / "sample-sitting.segments.txt"
# Private mode finds the photo folder (a neighboring line) and the venue call, and passes on
# the headline line (a miss).
TODO_WORDS = ("photo folder", "call the venue")


class FakeModel:
    choice = {"model": "stub", "low_ram": False}

    def __init__(self, *_):
        self._session = None

    def odds(self, system, user):
        target = user.split("[[", 1)[1].split("]]", 1)[0]
        return (5.0 if any(w in target for w in TODO_WORDS) else -20.0), 0.0

    def ask(self, system, user, max_tokens):
        if system == quality_bar.ml.SUMMARY_PROMPT:
            return json.dumps({"summary": "Newsletter check-in."}), 0.0
        return user.split("[[", 1)[1].split("]]", 1)[0], 0.0

    def close(self):
        pass


class QualityBarTest(unittest.TestCase):
    def test_report_counts(self):
        with tempfile.TemporaryDirectory() as d:
            sitting = Path(d) / "newsletter"
            sitting.mkdir()
            shutil.copy(FIXTURE, sitting / "transcript.txt")
            (sitting / "agent-items.json").write_text(json.dumps({"action_items": [
                {"task": "Send photos", "quote": "I'll send you the photo folder by Friday."},
                {"task": "Check dates", "quote": "Can you also check the event dates with the venue?"},
                {"task": "Headline", "quote": "Then we need to pick a headline before the layout goes out."},
                {"task": "Made up", "quote": "Nobody said this."}]}))
            out = Path(d) / "report.md"
            with mock.patch.object(quality_bar.ml, "LocalModel", FakeModel), \
                    mock.patch.object(quality_bar.local_model, "choose_model", lambda: FakeModel.choice):
                rc = quality_bar.main([str(sitting), "--out", str(out), "--no-clean"])
            text = out.read_text()
        # photos caught by photos, venue dates by call-the-venue (next line); headline is
        # missed (one Private item catches one Agent item); the made-up agent item never counts.
        self.assertIn("Catch rate: **2/3 = 67%**", text)
        self.assertIn("MISSED: Headline", text)
        self.assertIn("Precision: **2/2 = 100%**", text)
        self.assertIn("chance level", text)
        self.assertIn("quality bar — FAIL", text)
        self.assertIn("invented caught and dropped: 0", text)
        self.assertIn("Agent items dropped by the quote check (not counted): 1", text)
        self.assertEqual(rc, 1)

    def test_judged_verdicts_gate_release_and_beta(self):
        def run(caught, noise):
            return quality_bar.judged_verdict({"s1": {"agent_counted": 20, "caught": caught, "private_total": 30,
                                                      "match": caught, "real_extra": 0, "duplicate": 0, "noise": noise}})[1]
        self.assertEqual(run(16, 9), "PASS")   # 80% caught, 30% noise
        self.assertEqual(run(15, 15), "BETA")  # 75% caught, 50% noise
        self.assertEqual(run(15, 21), "FAIL")  # 75% caught, but 70% of the list is noise
        self.assertEqual(run(13, 3), "FAIL")   # 65% caught

    def test_judged_mode_reads_verdict_files_and_exits_0_for_beta(self):
        with tempfile.TemporaryDirectory() as d:
            v = Path(d) / "judge.json"
            v.write_text(json.dumps({"s4": {"agent_counted": 4, "caught": 3, "private_total": 6, "match": 3,
                                            "real_extra": 0, "duplicate": 1, "noise": 2, "misses": ["Pick a font"]}}))
            with mock.patch("sys.stdout"):
                self.assertEqual(quality_bar.main(["--judged", str(v)]), 0)
            v.write_text(json.dumps({"s4": {"agent_counted": 4, "caught": 1, "private_total": 6, "noise": 2}}))
            with mock.patch("sys.stdout"):
                self.assertEqual(quality_bar.main(["--judged", str(v)]), 1)

    def test_fails_under_bar(self):
        lines = quality_bar.ml.load_transcript(FIXTURE)
        far = [{"task": "x", "quote": "Thanks for jumping on."}]
        agent = [{"task": "y", "quote": "No, that's it. Talk soon."}]
        caught, missed, extra = quality_bar.match(agent, far, lines)
        self.assertEqual((len(caught), len(missed), len(extra)), (0, 1, 1))


if __name__ == "__main__":
    unittest.main()
