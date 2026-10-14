#!/usr/bin/env python3
"""meeting-loop MCP server — the Agent-mode front door for any MCP client
(Cursor, Claude Desktop, Windsurf, Claude Code).

Zero-dependency, hand-rolled JSON-RPC 2.0 over newline-delimited stdio (house
pattern). stdout is the protocol
channel; all logging goes to stderr.

This server holds no pipeline logic of its own. Every tool shells out to one
`meeting-loop` subcommand (non-interactive: stdin is always /dev/null, so a
question the CLI can't answer from flags takes its documented default or is
skipped — it never blocks waiting on a terminal that isn't there) and hands
back the subcommand's own MEETING_LOOP_RESULT / MEETING_LOOP_DOCTOR_RESULT
line as the tool's result. Audio and transcript text never leave this
machine through this server; only the AI driving the MCP client sees the
text it already asked for (same split as Private mode vs. Agent mode in the
spec).

Tools: find_recordings, transcribe, process, render_action_items, write_to_brain.
Resources (read-only): Profile, meeting types.
Prompt: meeting-loop — the client-neutral loop instructions below.

Self-check:  python3 server.py --selfcheck
"""
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
CLI = SKILL / "bin" / "meeting-loop"
MEETING_TYPES_PATH = SKILL / "meeting-types.json"
RESULT_PREFIXES = ("MEETING_LOOP_RESULT ", "MEETING_LOOP_DOCTOR_RESULT ")
CLI_TIMEOUT = 1800  # transcription on a long recording can take a while


def log(*a):
    sys.stderr.write("[meeting-loop-mcp] " + " ".join(str(x) for x in a) + "\n")


class ToolError(Exception):
    pass


# ---------------------------------------------------------------- the CLI
def run_cli(argv):
    """Run one `meeting-loop` subcommand, non-interactively, and return its
    own result JSON. Never raises on a reported failure (ok: false) -- that
    is data for the caller, not a server error; it raises ToolError only
    when the CLI produced no result line at all (a crash before it could)."""
    if not CLI.exists():
        raise ToolError(f"meeting-loop command not found at {CLI}")
    proc = subprocess.run(
        [str(CLI), *argv], capture_output=True, text=True,
        stdin=subprocess.DEVNULL, timeout=CLI_TIMEOUT,
    )
    for line in reversed(proc.stdout.splitlines()):
        for prefix in RESULT_PREFIXES:
            if line.startswith(prefix):
                try:
                    return json.loads(line[len(prefix):])
                except json.JSONDecodeError:
                    break
    reason = proc.stderr.strip() or f"no result line (exit {proc.returncode})"
    raise ToolError(f"meeting-loop {argv[0]} failed: {reason}")


# ---------------------------------------------------------------- tools
def t_find_recordings(args):
    folder = (args.get("folder") or "").strip()
    if not folder:
        raise ToolError("folder is required")
    return run_cli(["find", folder])


def t_transcribe(args):
    recording = (args.get("recording") or "").strip()
    if not recording:
        raise ToolError("recording is required")
    argv = ["transcribe", recording]
    if args.get("out"):
        argv += ["--out", args["out"]]
    return run_cli(argv)


def t_process(args):
    recordings = args.get("recordings")
    if not recordings or not isinstance(recordings, list):
        raise ToolError("recordings (a list of one or more paths) is required")
    argv = ["process", *(str(r) for r in recordings)]
    if args.get("type"):
        argv += ["--type", args["type"]]
    if args.get("no_entity"):
        argv += ["--no-entity"]
    elif args.get("entity"):
        argv += ["--entity", args["entity"]]
    if args.get("llm"):
        argv += ["--llm", args["llm"]]
    if args.get("agent_items"):
        argv += ["--agent-items", args["agent_items"]]
    if args.get("clean") is not None:
        argv += ["--clean" if args["clean"] else "--no-clean"]
    return run_cli(argv)


def t_render_action_items(args):
    items = (args.get("items") or "").strip()
    if not items:
        raise ToolError("items is required")
    argv = ["render", items]
    if args.get("out"):
        argv += ["--out", args["out"]]
    return run_cli(argv)


def t_write_to_brain(args):
    note = (args.get("note") or "").strip()
    if not note:
        raise ToolError("note is required")
    text, file = args.get("text"), args.get("file")
    if not text and not file:
        raise ToolError("text or file is required")
    argv = ["write", note, *(["--file", file] if file else ["--text", text])]
    return run_cli(argv)


TOOLS = [
    {
        "name": "find_recordings",
        "description": (
            "Find recordings in a folder and propose which ones belong to the same sitting "
            "(recordings close together in time). This only proposes -- always show the "
            "grouping and ask whether it looks right before transcribing or processing anything."
        ),
        "inputSchema": {"type": "object", "properties": {
            "folder": {"type": "string", "description": "Folder to search for recordings."},
        }, "required": ["folder"]},
    },
    {
        "name": "transcribe",
        "description": "Transcribe one recording to a timestamped transcript file.",
        "inputSchema": {"type": "object", "properties": {
            "recording": {"type": "string", "description": "Path to the recording."},
            "out": {"type": "string", "description": "Where to write the transcript. Default: beside the recording."},
        }, "required": ["recording"]},
    },
    {
        "name": "process",
        "description": (
            "Turn one or more recordings (already confirmed as one sitting) into a transcript, "
            "action items, and -- only when a Brain-relative note name is given -- a dated entry "
            "in that note. In Agent mode, do your own synthesis first and pass your candidate "
            "action items (each with its exact quote) via llm=\"agent\" and agent_items (a path "
            "to a JSON file of {task, quote} objects); meeting-loop still verifies every quote "
            "against the transcript and drops any that don't match, and only names an owner the "
            "transcript actually names. Always ask which entity note (if any) this sitting "
            "belongs to before setting entity -- never guess it."
        ),
        "inputSchema": {"type": "object", "properties": {
            "recordings": {"type": "array", "items": {"type": "string"},
                            "description": "One or more recording/transcript paths making up one sitting."},
            "type": {"type": "string", "description": "Meeting type id (see the meeting types resource)."},
            "entity": {"type": "string", "description": "Entity note to append a dated entry to. Ask first; never assume one."},
            "no_entity": {"type": "boolean", "description": "Skip the entity note. Set this when the answer to 'which note?' was none."},
            "llm": {"type": "string", "enum": ["local", "none", "agent"],
                    "description": "agent: use your own candidate action items (see agent_items)."},
            "agent_items": {"type": "string", "description": "Path to a JSON file of your candidate action items, for llm=\"agent\"."},
            "clean": {"type": "boolean",
                      "description": "Clean up transcript wording with the on-device model (written beside the raw "
                                     "transcript, which is always kept). Omit for the default: on for 16 GB+ Macs "
                                     "with llm=\"local\", off on 8 GB Macs."},
        }, "required": ["recordings"]},
    },
    {
        "name": "render_action_items",
        "description": "Render an action-items JSON file into a self-contained, shareable HTML view.",
        "inputSchema": {"type": "object", "properties": {
            "items": {"type": "string", "description": "Path to the action-items JSON file."},
            "out": {"type": "string", "description": "Where to write the HTML. Default: beside the JSON file."},
        }, "required": ["items"]},
    },
    {
        "name": "write_to_brain",
        "description": (
            "Append a dated block to one named note in the user's Brain. Never overwrites: an "
            "existing note gets the new block appended below what's already there. Only call this "
            "after the user has approved the exact text and named the note -- never on your own."
        ),
        "inputSchema": {"type": "object", "properties": {
            "note": {"type": "string", "description": "Path relative to the Brain root, e.g. Entities/acme.md."},
            "text": {"type": "string", "description": "The text to append."},
            "file": {"type": "string", "description": "Read the text to append from this file instead of text."},
        }, "required": ["note"]},
    },
]

HANDLERS = {
    "find_recordings": t_find_recordings,
    "transcribe": t_transcribe,
    "process": t_process,
    "render_action_items": t_render_action_items,
    "write_to_brain": t_write_to_brain,
}


# ---------------------------------------------------------------- resources
def profile_path():
    override = os.environ.get("MEETING_LOOP_PROFILE")
    return Path(override).expanduser() if override else Path.home() / ".meeting-loop" / "profile.json"


def r_profile(_uri):
    path = profile_path()
    if not path.exists():
        return json.dumps({
            "exists": False,
            "note": "no Profile yet; it is created automatically with recommended defaults the "
                     "first time a process or write_to_brain call needs one",
        })
    return path.read_text()


def r_meeting_types(_uri):
    return MEETING_TYPES_PATH.read_text()


RESOURCES = [
    {
        "uri": "meeting-loop://profile",
        "name": "Profile",
        "description": "The user's Meeting Loop settings (Brain location, mics, meeting types). Read-only here.",
        "mimeType": "application/json",
    },
    {
        "uri": "meeting-loop://meeting-types",
        "name": "Meeting types",
        "description": "The known meeting types and what each one shapes output into.",
        "mimeType": "application/json",
    },
]

RESOURCE_READERS = {
    "meeting-loop://profile": r_profile,
    "meeting-loop://meeting-types": r_meeting_types,
}


# ---------------------------------------------------------------- prompt
PROMPT_TEXT = """\
You are running Meeting Loop in Agent mode: you do the thinking (reading the \
transcript, summarizing, drafting action items), and the tools on this server \
do the local work (finding recordings, transcribing, writing into the user's \
Brain). Audio never has to leave this machine to reach you -- only the \
transcript text does, because you need it to think.

Follow this loop, and ask rather than assume at every decision point below:

1. Find the recording(s). If the user pointed at a folder, call find_recordings \
on it. If it proposes grouping more than one recording into the same sitting, \
show the proposed groups and ask whether that's right before going further -- \
never assume several files belong together, or that they don't.
2. If a recording isn't already a transcript, call transcribe on it.
3. Read the transcript yourself and ask which meeting type this is (client, \
personal, creative, dev, work, or another known type -- see the meeting types \
resource) unless it's already obvious and you say which one and why.
4. Write your own summary and candidate action items. Every action item needs \
the exact quote it came from -- don't paraphrase the quote, copy the words. \
Only name an owner when the transcript actually names one; otherwise leave it \
unassigned. Save your candidates as a small JSON file (a list of objects with \
at least task and quote).
5. Call process with your recordings, the confirmed type, and llm="agent" plus \
agent_items pointing at that JSON file. meeting-loop will verify every quote \
against the transcript itself and drop anything that doesn't match -- trust \
that check over your own judgment about which items survive.
6. Ask the user which entity note (if any) this sitting belongs to. Never \
guess a name or assume there is one. Pass entity only when they named one; \
otherwise pass no_entity.
7. Show the user the resulting summary and action items before doing anything \
else with them. If they want a shareable view, call render_action_items.
8. Action items are not automatic to-dos. For anything that would act in the \
world -- sending a message, filing something elsewhere, writing to a note the \
user didn't already approve -- describe exactly what you'd do and wait for an \
explicit go-ahead before you do it. write_to_brain itself should only ever be \
called with text the user has already seen and approved, appended to a note \
they named.

Never treat an action item as already approved just because it passed the \
quote check -- the quote check only proves it was really said, not that the \
user wants it acted on.
"""

PROMPTS = [
    {
        "name": "meeting-loop",
        "description": "Run the Meeting Loop end to end using this server's tools: find, transcribe, synthesize, confirm, and write to the Brain.",
        "arguments": [],
    },
]


# ---------------------------------------------------------------- JSON-RPC
def send(msg):
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def handle(msg):
    mid, method, params = msg.get("id"), msg.get("method"), msg.get("params") or {}
    if method == "initialize":
        return send({"jsonrpc": "2.0", "id": mid, "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}, "resources": {}, "prompts": {}},
            "serverInfo": {"name": "meeting-loop", "version": "1.0.0"},
        }})
    if method == "notifications/initialized":
        return  # a notification gets no response at all
    if method == "ping":
        return send({"jsonrpc": "2.0", "id": mid, "result": {}})

    if method == "tools/list":
        return send({"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOLS}})
    if method == "tools/call":
        name = params.get("name")
        fn = HANDLERS.get(name)
        if not fn:
            return send({"jsonrpc": "2.0", "id": mid, "result": {
                "content": [{"type": "text", "text": json.dumps(
                    {"error": "BAD_ARGS", "message": f"Unknown tool: {name}"})}],
                "isError": True}})
        try:
            value, err = fn(params.get("arguments") or {}), False
        except Exception as e:
            value, err = {"error": type(e).__name__, "message": str(e)}, True
            log(f"tool {name} error: {e}")
        return send({"jsonrpc": "2.0", "id": mid, "result": {
            "content": [{"type": "text", "text": json.dumps(value, default=str)}],
            "isError": err}})

    if method == "resources/list":
        return send({"jsonrpc": "2.0", "id": mid, "result": {"resources": RESOURCES}})
    if method == "resources/read":
        uri = params.get("uri")
        reader = RESOURCE_READERS.get(uri)
        if not reader:
            return send({"jsonrpc": "2.0", "id": mid,
                         "error": {"code": -32602, "message": f"Unknown resource: {uri}"}})
        try:
            text = reader(uri)
        except OSError as e:
            return send({"jsonrpc": "2.0", "id": mid,
                         "error": {"code": -32603, "message": str(e)}})
        return send({"jsonrpc": "2.0", "id": mid, "result": {
            "contents": [{"uri": uri, "mimeType": "application/json", "text": text}]}})

    if method == "prompts/list":
        return send({"jsonrpc": "2.0", "id": mid, "result": {"prompts": PROMPTS}})
    if method == "prompts/get":
        name = params.get("name")
        if name != "meeting-loop":
            return send({"jsonrpc": "2.0", "id": mid,
                         "error": {"code": -32602, "message": f"Unknown prompt: {name}"}})
        return send({"jsonrpc": "2.0", "id": mid, "result": {
            "description": PROMPTS[0]["description"],
            "messages": [{"role": "user", "content": {"type": "text", "text": PROMPT_TEXT}}],
        }})

    if mid is not None:
        send({"jsonrpc": "2.0", "id": mid,
              "error": {"code": -32601, "message": f"Method not found: {method}"}})


def selfcheck():
    assert MEETING_TYPES_PATH.exists()
    assert CLI.exists()
    assert len(TOOLS) == 5
    assert {t["name"] for t in TOOLS} == set(HANDLERS)
    assert len(RESOURCES) == 2
    assert PROMPTS[0]["name"] == "meeting-loop"
    for forbidden in ("Claude Code", "Bash tool", "Read tool", "the Task tool", "subagent"):
        assert forbidden not in PROMPT_TEXT, f"prompt names a harness-specific tool: {forbidden!r}"
    try:
        t_find_recordings({})
        raise AssertionError("accepted a missing folder")
    except ToolError:
        pass
    try:
        t_write_to_brain({"note": "x.md"})
        raise AssertionError("accepted write_to_brain with neither text nor file")
    except ToolError:
        pass
    print("selfcheck ok")


def main():
    log(f"ready · {len(TOOLS)} tools · {len(RESOURCES)} resources · {len(PROMPTS)} prompt")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            log(f"bad JSON: {line[:120]}")
            continue
        try:
            handle(msg)
        except Exception as e:
            log(f"handler error: {e}")
            if msg.get("id") is not None:
                send({"jsonrpc": "2.0", "id": msg["id"],
                      "error": {"code": -32603, "message": str(e)}})


if __name__ == "__main__":
    selfcheck() if "--selfcheck" in sys.argv else main()
