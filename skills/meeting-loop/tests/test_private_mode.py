"""Private mode's model-free logic: which model a Mac gets, how a long transcript is
cut into chunks, how the model's replies are read and merged, and the 8 GB note.

The model itself never runs here (that is tests/slow_private_mode.py, opt-in).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import local_model  # noqa: E402
import meeting_loop  # noqa: E402

GB = 2 ** 30


class OfflineModelTest(unittest.TestCase):
    """Private mode runs offline (HF_HUB_OFFLINE) once the Whisper model is in the cache."""

    def test_cached_only_when_a_snapshot_is_present(self):
        import os, tempfile
        with tempfile.TemporaryDirectory() as tmp:
            old = os.environ.get("HF_HUB_CACHE")
            os.environ["HF_HUB_CACHE"] = tmp
            try:
                self.assertFalse(meeting_loop.whisper_model_cached())
                snap = Path(tmp) / "models--mlx-community--whisper-large-v3-turbo" / "snapshots" / "abc"
                snap.mkdir(parents=True)
                (snap / "config.json").write_text("{}")
                self.assertTrue(meeting_loop.whisper_model_cached())
            finally:
                os.environ.pop("HF_HUB_CACHE") if old is None else os.environ.__setitem__("HF_HUB_CACHE", old)


class ModelChoiceTest(unittest.TestCase):
    def test_16gb_and_up_gets_qwen3_8b_and_no_note(self):
        for gb in (16, 24, 64):
            choice = local_model.choose_model(gb * GB, env={})
            self.assertEqual(choice["model"], "mlx-community/Qwen3-8B-4bit")
            self.assertFalse(choice["low_ram"])

    def test_under_16gb_gets_qwen3_4b_and_is_low_ram(self):
        for gb in (8, 12):
            choice = local_model.choose_model(gb * GB, env={})
            self.assertEqual(choice["model"], "mlx-community/Qwen3-4B-4bit")
            self.assertTrue(choice["low_ram"])

    def test_ram_override_lets_a_16gb_mac_take_the_8gb_path(self):
        choice = local_model.choose_model(16 * GB, env={"MEETING_LOOP_RAM_GB": "8"})
        self.assertEqual(choice["model"], "mlx-community/Qwen3-4B-4bit")
        self.assertTrue(choice["low_ram"])


class ChunkTest(unittest.TestCase):
    def test_short_transcript_is_one_chunk(self):
        self.assertEqual(local_model.chunks(["a" * 10, "b" * 10], max_chars=100), [(0, 2)])

    def test_long_transcript_splits_on_whole_lines_in_order_within_budget(self):
        texts = ["x" * 40] * 10  # 40 chars + newline each
        spans = local_model.chunks(texts, max_chars=100)
        self.assertEqual(spans, [(0, 2), (2, 4), (4, 6), (6, 8), (8, 10)])

    def test_a_line_longer_than_the_budget_gets_its_own_chunk(self):
        spans = local_model.chunks(["short", "y" * 500, "short"], max_chars=100)
        self.assertEqual(spans, [(0, 1), (1, 2), (2, 3)])


class ReadReplyTest(unittest.TestCase):
    def test_reads_a_json_object_wrapped_in_thinking_fences_and_chatter(self):
        reply = ('<think>\nLet me look.\n</think>\nHere you go:\n```json\n'
                 '{"summary": "Newsletter check-in.", "action_items": [{"task": "Send photos", "quote": "I\'ll send"}]}\n'
                 '```\nHope that helps.')
        self.assertEqual(local_model.read_json(reply), {
            "summary": "Newsletter check-in.",
            "action_items": [{"task": "Send photos", "quote": "I'll send"}]})

    def test_unreadable_reply_is_none(self):
        for reply in ("", "no json here", '{"summary": "cut off', "[1, 2]"):
            self.assertIsNone(local_model.read_json(reply), reply)


def line(text, speaker="Host", ts="00:00"):
    return {"ts": ts, "speaker": speaker, "text": text}


class MomentTest(unittest.TestCase):
    def test_the_line_is_bracketed_among_its_neighbors_as_speaker_turns(self):
        lines = [line("ok so"), line("I'll send you the deck"), line("cool", "Guest")]
        self.assertEqual(meeting_loop._moment(lines, 1),
                         "Host: ok so [[I'll send you the deck]]\nGuest: cool")

    def test_lines_past_the_character_budget_are_left_out(self):
        lines = [line("x" * 900), line("I'll send it"), line("y" * 900, "Guest")]
        self.assertEqual(meeting_loop._moment(lines, 1), "Host: [[I'll send it]]")


class CheckTaggedTest(unittest.TestCase):
    def test_cue_lines_at_or_over_the_odds_bar_become_items_quoting_that_line(self):
        lines = [line("nice weather"), line("I'll send you the deck"),
                 line("we should grab lunch sometime"), line("can you call the venue", "Guest")]
        odds = {"deck": 2.0, "lunch": -12.0, "venue": meeting_loop.TODO_ODDS[False]}
        scored = []

        class Model:
            choice = {"model": "stub", "low_ram": False}

            def odds(self, system, user):
                target = user.split("[[", 1)[1].split("]]", 1)[0]
                scored.append(target)
                return next(v for k, v in odds.items() if k in target), 0.0

            def ask(self, system, user, max_tokens):
                target = user.split("[[", 1)[1].split("]]", 1)[0]
                return ('"[[Send the deck]]"' if "deck" in target else ""), 0.0

        items = meeting_loop.check_tagged(lines, Model())
        self.assertEqual(scored, [l["text"] for l in lines[1:]])  # "nice weather" has no cue
        self.assertEqual(items, [
            {"task": "Send the deck", "quote": "I'll send you the deck", "at": 1},
            {"task": "can you call the venue", "quote": "can you call the venue", "at": 3}])


    def test_the_odds_prompt_is_one_paragraph_as_the_bars_were_set_on(self):
        # a line break moves Qwen3-4B's odds by 10+ points, which would void the bar
        self.assertNotIn("\n", meeting_loop.ODDS_PROMPT)
        self.assertTrue(meeting_loop.ODDS_PROMPT.endswith("Answer yes or no."))

    def test_the_8gb_model_has_its_own_bar(self):
        self.assertGreater(meeting_loop.TODO_ODDS[True], meeting_loop.TODO_ODDS[False])


class BetaNoteTest(unittest.TestCase):
    def note(self, low_ram):
        class Model:
            choice = {"model": "stub", "low_ram": low_ram}

            def ask(self, system, user, max_tokens):
                return '{"summary": "Check-in."}', 0.0

            def odds(self, system, user):
                return -20.0, 0.0

        return meeting_loop.synthesize_local([line("I'll send the deck")], Model())["note"]

    def test_private_mode_always_says_it_is_a_beta_list_to_check(self):
        note = self.note(low_ram=False)
        self.assertIn("Private mode is in beta", note)
        self.assertIn("Check each one against its quote.", note)
        self.assertNotIn("less refined", note)

    def test_the_8gb_note_follows_the_beta_note(self):
        note = self.note(low_ram=True)
        self.assertTrue(note.startswith(meeting_loop.BETA_NOTE))
        self.assertTrue(note.endswith(local_model.LOW_RAM_NOTE))


class QuoteCheckLineTest(unittest.TestCase):
    def test_quote_check_places_an_item_on_its_own_line_when_the_words_repeat(self):
        lines = [line("I'll send you the deck", "Host", "00:01"),
                 line("I'll send you the deck", "Guest", "00:09")]
        kept, dropped = meeting_loop.quote_check(
            [{"task": "Send the deck", "quote": "I'll send you the deck", "at": 1}], lines)
        self.assertEqual((dropped, kept[0]["ts"], kept[0]["owner"]), (0, "00:09", "Guest"))


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "sample-sitting.segments.txt"
RAW = FIXTURE.read_text().splitlines()


def prefix(line):
    """'[a -> b] Speaker: ' -- everything before the words, from a known-good raw line."""
    return line[:line.index(": ") + 2] if ": " in line else line[:line.index("] ") + 2]


class CleanupAlignTest(unittest.TestCase):
    """Cleanup keeps every timestamp and speaker label; only the words may change."""

    def setUp(self):
        self.lines = meeting_loop.load_transcript(FIXTURE)

    def assert_labels_match_raw(self, cleaned):
        self.assertEqual(len(cleaned), len(self.lines))
        for raw, new in zip(self.lines, cleaned):
            self.assertEqual((new["ts"], new["speaker"]), (raw["ts"], raw["speaker"]))
            self.assertTrue(new["line"].startswith(prefix(raw["line"])), new["line"])

    def test_reworded_lines_with_the_same_timestamp_and_speaker_are_kept(self):
        reply = "\n".join(RAW).replace("Quick one today, just", "Quick one today:").replace(
            "Sure. The draft", "Sure, the draft")
        cleaned, fallbacks = meeting_loop.align_cleaned(self.lines, reply)
        self.assertEqual(fallbacks, 0)
        self.assert_labels_match_raw(cleaned)
        self.assertEqual(cleaned[0]["line"],
                         "[00:00:00.000 -> 00:00:04.200] Host: Thanks for jumping on. Quick one today: the spring newsletter.")
        self.assertEqual(cleaned[1]["text"], "Sure, the draft is mostly done, the photos are the holdup.")

    def test_a_changed_timestamp_or_speaker_falls_back_to_the_raw_line(self):
        reply = RAW[:]
        reply[2] = "[00:00:09.000 -> 00:00:14.500] Host: I'll send the photo folder Friday."   # timestamp moved
        reply[3] = "[00:00:14.500 -> 00:00:19.100] Host: Great. Can you check the dates?"     # speaker swapped
        cleaned, fallbacks = meeting_loop.align_cleaned(self.lines, "\n".join(reply))
        self.assertEqual(fallbacks, 2)
        self.assert_labels_match_raw(cleaned)
        self.assertEqual(cleaned[2]["line"], RAW[2])
        self.assertEqual(cleaned[3]["line"], RAW[3])

    def test_a_dropped_line_or_added_chatter_does_not_shift_the_other_lines(self):
        reply = ["Here is the cleaned transcript:"] + RAW[:4] + RAW[5:] + ["Hope this helps!"]  # line 4 dropped
        reply[1] = reply[1].replace("Thanks for jumping on.", "Thanks for joining.")
        cleaned, fallbacks = meeting_loop.align_cleaned(self.lines, "\n".join(reply))
        self.assertEqual(fallbacks, 1)
        self.assert_labels_match_raw(cleaned)
        self.assertIn("Thanks for joining.", cleaned[0]["line"])
        self.assertEqual(cleaned[4]["line"], RAW[4])
        self.assertEqual(cleaned[7]["line"], RAW[7])

    def test_a_speaker_label_invented_for_an_unlabeled_line_falls_back(self):
        lines = meeting_loop.load_transcript_text("[00:00:00.000 -> 00:00:03.000] so um we should start\n")
        reply = "[00:00:00.000 -> 00:00:03.000] Host: So we should start."
        cleaned, fallbacks = meeting_loop.align_cleaned(lines, reply)
        self.assertEqual(fallbacks, 1)
        self.assertEqual(cleaned[0]["line"], "[00:00:00.000 -> 00:00:03.000] so um we should start")


class CleanTranscriptOutputTest(unittest.TestCase):
    def outputs(self, cleaned):
        lines = meeting_loop.load_transcript(FIXTURE)
        synth = {"summary": None, "action_items": []}
        return dict(meeting_loop.sitting_outputs([(FIXTURE, lines, cleaned)], synth, FIXTURE,
                                                 meeting_loop.datetime.datetime.now(), "work", "local"))

    def test_cleaned_transcript_is_written_beside_the_raw_one_which_stays_raw(self):
        lines = meeting_loop.load_transcript(FIXTURE)
        cleaned, _ = meeting_loop.align_cleaned(lines, "\n".join(RAW).replace("Quick one today, just", "Quick one today:"))
        out = self.outputs(cleaned)
        raw = next(t for p, t in out.items() if p.endswith("/transcript.md"))
        clean_path = next(p for p in out if p.endswith("/transcript-clean.md"))
        self.assertEqual(Path(clean_path).parent, Path(next(p for p in out if p.endswith("/transcript.md"))).parent)
        for line in RAW:
            self.assertIn(line, raw)
        self.assertIn("Quick one today: the spring newsletter.", out[clean_path])
        self.assertNotIn("Quick one today:", raw)

    def test_no_cleaned_transcript_when_cleanup_did_not_run(self):
        self.assertFalse([p for p in self.outputs(None) if "clean" in p])


class LowRamNoteTest(unittest.TestCase):
    FIXTURE = Path(__file__).resolve().parent / "fixtures" / "sample-sitting.segments.txt"

    def outputs(self, note):
        lines = meeting_loop.load_transcript(self.FIXTURE)
        synth = {"summary": "Newsletter check-in.", "note": note, "action_items": [
            {"task": "Send photos", "quote": "I'll send you the photo folder by Friday.",
             "owner": "Host", "speaker": "Host", "ts": "00:00:09.800"}]}
        return dict(meeting_loop.sitting_outputs([(self.FIXTURE, lines, None)], synth, self.FIXTURE,
                                                 meeting_loop.datetime.datetime.now(), "meeting", "local"))

    def test_8gb_note_is_in_notes_and_the_action_items_view(self):
        out = self.outputs(local_model.LOW_RAM_NOTE)
        notes = next(t for p, t in out.items() if p.endswith("notes.md"))
        html = next(t for p, t in out.items() if p.endswith(".html"))
        self.assertIn("simpler and less refined on this Mac", notes)
        self.assertIn("simpler and less refined on this Mac", html)
        self.assertIn("Newsletter check-in.", notes)

    def test_no_note_on_a_16gb_run(self):
        for path, text in self.outputs(None).items():
            self.assertNotIn("less refined", text, path)


if __name__ == "__main__":
    unittest.main()
