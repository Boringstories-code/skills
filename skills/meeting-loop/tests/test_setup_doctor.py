"""Seam: `meeting-loop setup` and `meeting-loop doctor`, driven as a user would.

Each test runs the real command in a subprocess with HOME pointed at a
throwaway folder (so the default Profile and Brain land there) and, for
`doctor`'s version check, MEETING_LOOP_VERSION_URL pointed at a local
file:// URL so the suite stays offline.
"""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
CMD = SKILL / "bin" / "meeting-loop"
DOCTOR_PREFIX = "MEETING_LOOP_DOCTOR_RESULT "
VERSION_FILE = SKILL / "VERSION"


def run(home, *args, env_extra=None):
    env = {k: v for k, v in os.environ.items() if not k.startswith("MEETING_LOOP")}
    env["HOME"] = str(home)
    env.update(env_extra or {})
    return subprocess.run([str(CMD), *args], capture_output=True, text=True, env=env, timeout=60,
                          stdin=subprocess.DEVNULL)  # no terminal: questions get EOF, never block


def doctor_result(proc):
    last = proc.stdout.rstrip("\n").splitlines()[-1]
    assert last.startswith(DOCTOR_PREFIX), f"last line not machine-readable: {last!r}"
    return json.loads(last[len(DOCTOR_PREFIX):])


class SetupTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)
        self.profile_path = self.home / ".meeting-loop" / "profile.json"

    def tearDown(self):
        self._tmp.cleanup()

    def test_accepting_defaults_writes_a_schema_valid_profile(self):
        proc = run(self.home, "setup", "--yes")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(self.profile_path.is_file())
        data = json.loads(self.profile_path.read_text())
        self.assertEqual(data["version"], 1)
        self.assertEqual(data["brain"]["root"], str(self.home / "MeetingLoop" / "Brain"))
        self.assertEqual(data["install"]["kind"], "person")

        sys_path = [str(SKILL / "scripts")]
        import sys
        for p in sys_path:
            if p not in sys.path:
                sys.path.insert(0, p)
        import importlib
        profile_mod = importlib.import_module("ml_profile")
        errors = profile_mod.validate(data, profile_mod.schema())
        self.assertEqual(errors, [], errors)

    def test_protected_folder_brain_triggers_warning(self):
        protected = self.home / "Documents" / "MeetingLoopBrain"
        proc = run(self.home, "setup", "--yes", "--brain", str(protected))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("protected location", proc.stdout)
        self.assertIn("Privacy", proc.stdout)

    def test_custom_mics_and_types_are_saved(self):
        proc = run(self.home, "setup", "--yes", "--mics", "two", "--types", "client,work")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(self.profile_path.read_text())
        self.assertEqual(data["capture"]["method"], "two-mic")
        self.assertEqual(data["capture"]["attribution_expectation"], "full")
        self.assertEqual(data["decisions"][0]["answer"], ["client", "work"])

    def test_unknown_meeting_type_stops_with_plain_message(self):
        proc = run(self.home, "setup", "--yes", "--types", "not-a-real-type")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("unknown meeting type", proc.stderr)
        self.assertFalse(self.profile_path.exists())


class MigrationTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)
        self.profile_path = self.home / ".meeting-loop" / "profile.json"
        self.profile_path.parent.mkdir(parents=True)

    def tearDown(self):
        self._tmp.cleanup()

    def _legacy_profile(self):
        # Same shape as a v1 Profile but with the version field missing
        # entirely, standing in for a Profile written before it existed.
        return {
            "install": {"id": "legacy", "kind": "person", "display_name": "Legacy Lee", "created": "2026-01-01"},
            "owner": {"mode": "single", "name": "Legacy Lee"},
            "environment": {"asr": {"engine": "mlx-whisper"}},
            "brain": {"adapter": "plain-folders", "root": str(self.home / "Legacy" / "Brain"),
                      "capability": "direct-write"},
            "distillation": {"level": "L0"},
            "privacy": {"destination_shared": False, "audience": "solo-sync"},
            "capture": {"method": "single-mic-worn"},
            "execution": {"enabled": False},
        }

    def test_older_version_profile_is_migrated_with_answers_preserved(self):
        self.profile_path.write_text(json.dumps(self._legacy_profile()))
        proc = run(self.home, "doctor", env_extra={"MEETING_LOOP_VERSION_URL": f"file://{VERSION_FILE}"})
        self.assertEqual(proc.returncode, 0, proc.stderr)

        migrated = json.loads(self.profile_path.read_text())
        self.assertEqual(migrated["version"], 1)
        self.assertEqual(migrated["owner"]["name"], "Legacy Lee")
        self.assertEqual(migrated["brain"]["root"], str(self.home / "Legacy" / "Brain"))

    def test_future_version_profile_stops_with_plain_message(self):
        future = self._legacy_profile()
        future["version"] = 999
        self.profile_path.write_text(json.dumps(future))
        proc = run(self.home, "doctor", env_extra={"MEETING_LOOP_VERSION_URL": f"file://{VERSION_FILE}"})
        self.assertNotEqual(proc.returncode, 0)
        combined = proc.stdout + proc.stderr
        self.assertIn("newer", combined)


class DoctorTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_doctor_reports_pass_fail_per_check_and_version(self):
        run(self.home, "setup", "--yes")
        proc = run(self.home, "doctor", env_extra={"MEETING_LOOP_VERSION_URL": f"file://{VERSION_FILE}"})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = doctor_result(proc)
        names = {c["name"] for c in result["checks"]}
        self.assertEqual(names, {"profile", "brain", "ffmpeg", "version"})
        version_check = next(c for c in result["checks"] if c["name"] == "version")
        self.assertIn("up to date", version_check["detail"])

    def test_doctor_version_check_only_runs_in_doctor(self):
        proc = run(self.home, "process", "--llm", "none", str(SKILL / "tests" / "fixtures" / "sample-sitting.segments.txt"),
                   env_extra={"MEETING_LOOP_VERSION_URL": "file:///does/not/exist"})
        self.assertEqual(proc.returncode, 0, proc.stderr)  # a bad version URL never affects `process`

    def test_doctor_with_no_profile_fails_profile_check_without_creating_one(self):
        proc = run(self.home, "doctor", env_extra={"MEETING_LOOP_VERSION_URL": f"file://{VERSION_FILE}"})
        self.assertNotEqual(proc.returncode, 0)
        result = doctor_result(proc)
        profile_check = next(c for c in result["checks"] if c["name"] == "profile")
        self.assertFalse(profile_check["ok"])
        self.assertFalse((self.home / ".meeting-loop" / "profile.json").exists())


if __name__ == "__main__":
    unittest.main()
