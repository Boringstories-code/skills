"""Seam 2: the MCP server (Skills/meeting-loop/mcp/server.py). Raw JSON-RPC
piped in over stdio, same house style as the stdio servers it's modeled on. The server itself holds no logic -- every assertion
here is really checking that it hands the real `meeting-loop` subcommands'
own results back unchanged.
"""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
SERVER = SKILL / "mcp" / "server.py"
FIXTURE = SKILL / "tests" / "fixtures" / "sample-sitting.segments.txt"


class Client:
    """One server subprocess, driven by writing JSON-RPC lines to its stdin
    and reading replies from its stdout -- no SDK, just the protocol."""

    def __init__(self, home, **extra_env):
        env = {k: v for k, v in os.environ.items() if not k.startswith("MEETING_LOOP")}
        env["HOME"] = str(home)
        env.update(extra_env)
        self.proc = subprocess.Popen(
            ["python3", str(SERVER)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, bufsize=1, env=env,
        )
        self._id = 0

    def close(self):
        self.proc.stdin.close()
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        self.proc.stdout.close()
        self.proc.stderr.close()

    def _next_id(self):
        self._id += 1
        return self._id

    def request(self, method, params=None):
        mid = self._next_id()
        self.proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": mid, "method": method,
                                           "params": params or {}}) + "\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        assert line, f"no reply to {method} (stderr: {self.proc.stderr.read()})"
        reply = json.loads(line)
        assert reply.get("id") == mid, reply
        return reply

    def notify(self, method, params=None):
        self.proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": method,
                                           "params": params or {}}) + "\n")
        self.proc.stdin.flush()

    def call_tool(self, name, arguments=None):
        reply = self.request("tools/call", {"name": name, "arguments": arguments or {}})
        result = reply["result"]
        value = json.loads(result["content"][0]["text"])
        return value, result["isError"]


class McpServerTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)
        self.client = Client(self.home)

    def tearDown(self):
        self.client.close()
        self._tmp.cleanup()

    def test_initialize_then_initialized_notification(self):
        reply = self.client.request("initialize")
        self.assertEqual(reply["result"]["serverInfo"]["name"], "meeting-loop")
        self.client.notify("notifications/initialized")  # must not hang or error

    def test_tools_list_returns_the_five_tools(self):
        reply = self.client.request("tools/list")
        names = {t["name"] for t in reply["result"]["tools"]}
        self.assertEqual(names, {
            "find_recordings", "transcribe", "process", "render_action_items", "write_to_brain",
        })

    def test_resources_list_returns_profile_and_meeting_types(self):
        reply = self.client.request("resources/list")
        uris = {r["uri"] for r in reply["result"]["resources"]}
        self.assertEqual(uris, {"meeting-loop://profile", "meeting-loop://meeting-types"})

    def test_prompts_list_returns_one_prompt(self):
        reply = self.client.request("prompts/list")
        names = [p["name"] for p in reply["result"]["prompts"]]
        self.assertEqual(names, ["meeting-loop"])

    def test_prompts_get_returns_client_neutral_instructions(self):
        reply = self.client.request("prompts/get", {"name": "meeting-loop"})
        text = reply["result"]["messages"][0]["content"]["text"]
        self.assertIn("ask", text.lower())
        for harness_word in ("Claude Code", "Bash tool", "subagent", "Task tool"):
            self.assertNotIn(harness_word, text)

    def test_resources_read_meeting_types(self):
        reply = self.client.request("resources/read", {"uri": "meeting-loop://meeting-types"})
        text = reply["result"]["contents"][0]["text"]
        data = json.loads(text)
        self.assertIn("types", data)

    def test_tools_call_process_on_the_fixture_produces_files(self):
        value, is_error = self.client.call_tool("process", {
            "recordings": [str(FIXTURE)], "llm": "none", "no_entity": True,
        })
        self.assertFalse(is_error, value)
        self.assertTrue(value["ok"], value)
        self.assertTrue(value["files"])
        for f in value["files"]:
            self.assertTrue(Path(f).is_file(), f)

    def test_process_clean_flag_reaches_the_command(self):
        self.client.close()
        self.client = Client(self.home, CML_ENV_DIR=str(self.home / "no-engine-here"))
        value, is_error = self.client.call_tool("process", {
            "recordings": [str(FIXTURE)], "llm": "none", "no_entity": True, "type": "work", "clean": True,
        })
        self.assertFalse(value["ok"], value)  # cleanup asked for the model, and this home has none
        self.assertIn("isn't set up", value["error"])
        value, _ = self.client.call_tool("process", {
            "recordings": [str(FIXTURE)], "llm": "none", "no_entity": True, "type": "work", "clean": False,
        })
        self.assertTrue(value["ok"], value)
        self.assertEqual(value["cleanup"], {"ran": False})

    def test_write_to_brain_called_twice_only_appends(self):
        first, err1 = self.client.call_tool("write_to_brain", {
            "note": "Entities/acme.md", "text": "first entry",
        })
        self.assertFalse(err1, first)
        note = Path(first["files"][0])
        before = note.read_text()
        self.assertIn("first entry", before)

        second, err2 = self.client.call_tool("write_to_brain", {
            "note": "Entities/acme.md", "text": "second entry",
        })
        self.assertFalse(err2, second)
        after = note.read_text()
        self.assertTrue(after.startswith(before), "second call did not append, it rewrote")
        self.assertIn("first entry", after)
        self.assertIn("second entry", after)

    def test_write_to_brain_without_text_or_file_is_a_tool_error(self):
        value, is_error = self.client.call_tool("write_to_brain", {"note": "Entities/acme.md"})
        self.assertTrue(is_error)
        self.assertIn("text or file", value["message"])

    def test_unknown_tool_is_a_tool_error_not_a_crash(self):
        reply = self.client.request("tools/call", {"name": "delete_everything", "arguments": {}})
        self.assertTrue(reply["result"]["isError"])


if __name__ == "__main__":
    unittest.main()
