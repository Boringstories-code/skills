#!/usr/bin/env python3
"""local_model.py — Private mode's on-device language model (MLX), and the seam to it.

Two halves in one file:
  * Caller side (stdlib, imported by meeting_loop.py): choose_model() picks the model
    the Mac's memory can run; Session(model) starts this file under the engine venv,
    loads the model once and answers ask(system, user) calls. Ticket 04's cleanup
    uses Session too. chunks() and read_json() are the shared model-free helpers.
  * Worker side (`python local_model.py MODEL`, engine venv, needs mlx-lm): loads MODEL
    from the local cache with the network off, prints {"loaded": secs}, then for each
    {"system", "user", "max_tokens"} line on stdin prints {"text", "secs"}.
    `--download [MODEL]` fetches a model once (setup time, telemetry off).
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

MODEL_LARGE = "mlx-community/Qwen3-8B-4bit"  # 16 GB+ Macs
MODEL_SMALL = "mlx-community/Qwen3-4B-4bit"  # under 16 GB (8 GB Macs)
RAM_OVERRIDE = "MEETING_LOOP_RAM_GB"  # pretend the Mac has this many GB (to try the 8 GB path)
LOW_RAM_NOTE = ("Results are simpler and less refined on this Mac: with under 16 GB of memory, "
                "Private mode runs a smaller model.")


def physical_ram():
    return int(subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True).stdout.strip() or 0)


def choose_model(mem_bytes=None, env=os.environ):
    """-> {"model": MLX repo id, "low_ram": bool}: 16 GB+ gets the 8B model, else the 4B."""
    gb = float(env[RAM_OVERRIDE]) if env.get(RAM_OVERRIDE) else (mem_bytes or physical_ram()) / 2 ** 30
    low = gb < 16
    return {"model": MODEL_SMALL if low else MODEL_LARGE, "low_ram": low}


def read_json(reply):
    """The first JSON object in a model reply (thinking, code fences and chatter
    around it are ignored) -> dict, or None when there isn't a readable one."""
    reply = re.sub(r"<think>.*?(</think>|$)", "", reply, flags=re.S)
    start = reply.find("{")
    while start != -1:
        try:
            obj, _ = json.JSONDecoder().raw_decode(reply, start)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass
        start = reply.find("{", start + 1)
    return None


def chunks(texts, max_chars):
    """-> [(start, end)] spans of whole lines, in order, each under max_chars joined
    with newlines (a single line longer than that gets a span of its own)."""
    spans, start, size = [], 0, 0
    for i, t in enumerate(texts):
        n = len(t) + 1
        if i > start and size + n > max_chars:
            spans.append((start, i))
            start, size = i, 0
        size += n
    if texts:
        spans.append((start, len(texts)))
    return spans


class ModelError(Exception):
    """A plain-language reason the local model couldn't run."""


NOT_SET_UP = "Private mode's model engine isn't set up: run `bash scripts/setup_env.sh`"
OFFLINE_ENV = {"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "HF_HUB_DISABLE_TELEMETRY": "1"}


def engine_python():
    """The engine venv's python (the same venv transcription uses), or ModelError."""
    env_dir = Path(os.environ.get("CML_ENV_DIR") or Path.home() / ".cache/mlx-whisper-transcribe/venv")
    python = env_dir / "bin" / "python"
    if not python.is_file():
        raise ModelError(NOT_SET_UP)
    return str(python)


class Session:
    """The on-device model, loaded once in the engine venv with the network off.

        with local_model.Session(model_id) as m:   # m.loaded = seconds the load took
            text, secs = m.ask(system, user, max_tokens)

    Raises ModelError with a plain reason when the engine or the model is missing.
    """

    def __init__(self, model):
        self._err = tempfile.TemporaryFile("w+")
        self._proc = subprocess.Popen([engine_python(), str(Path(__file__).resolve()), model], text=True,
                                      stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self._err,
                                      env=dict(os.environ, **OFFLINE_ENV))
        self.loaded = self._read()["loaded"]

    def ask(self, system, user, max_tokens=1024):
        """-> (reply text, seconds it took)."""
        self._proc.stdin.write(json.dumps({"system": system, "user": user, "max_tokens": max_tokens}) + "\n")
        self._proc.stdin.flush()
        reply = self._read()
        return reply["text"], reply["secs"]

    def odds(self, system, user):
        """-> (log-odds that the model's first word is yes rather than no, seconds it took).
        One forward pass, no generation: a score to set a bar on, not a free-text answer."""
        self._proc.stdin.write(json.dumps({"system": system, "user": user, "odds": True}) + "\n")
        self._proc.stdin.flush()
        reply = self._read()
        return reply["odds"], reply["secs"]

    def _read(self):
        line = self._proc.stdout.readline()
        if line:
            return json.loads(line)
        self._proc.wait()
        self._err.seek(0)
        said = [l[len("local_model: "):] for l in self._err.read().splitlines() if l.startswith("local_model: ")]
        raise ModelError(said[-1] if said else f"the local model stopped (exit {self._proc.returncode})")

    def close(self):
        if self._proc.poll() is None:
            self._proc.stdin.close()
            self._proc.wait()
        self._err.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def _die(msg):
    print(f"local_model: {msg}", file=sys.stderr)
    sys.exit(1)


def _emit(obj):
    print(json.dumps(obj), flush=True)


def _worker(model_id):
    os.environ.update(OFFLINE_ENV)  # before huggingface_hub is imported
    here = str(Path(__file__).resolve().parent)
    sys.path[:] = [p for p in sys.path if p and Path(p).resolve() != Path(here)]  # keep our scripts/ off the path: a module there could shadow a library name
    try:
        from mlx_lm import generate as mlx_generate, load
    except ImportError as e:
        _die(f"{NOT_SET_UP} ({e})")
    t = time.time()
    try:
        model, tok = load(model_id)
    except Exception as e:  # not in the local cache (the network is off) or a broken download
        _die(f"the local model {model_id} isn't downloaded yet; run setup first ({type(e).__name__})")
    _emit({"loaded": round(time.time() - t, 1)})
    for line in sys.stdin:
        p = json.loads(line)
        t = time.time()
        messages = [{"role": "system", "content": p["system"]}, {"role": "user", "content": p["user"]}]
        prompt = tok.apply_chat_template(messages, add_generation_prompt=True, tokenize=False,
                                         enable_thinking=False)  # Qwen3: answer directly, no <think> pass
        if p.get("odds"):
            import mlx.core as mx
            logits = model(mx.array([tok.encode(prompt)]))[0, -1]
            first = lambda words: mx.logsumexp(logits[mx.array([tok.encode(w)[0] for w in words])]).item()
            _emit({"odds": round(first(("yes", "Yes")) - first(("no", "No")), 3), "secs": round(time.time() - t, 2)})
            continue
        text = mlx_generate(model, tok, prompt=prompt, max_tokens=p.get("max_tokens", 1024), verbose=False)
        _emit({"text": text, "secs": round(time.time() - t, 1)})


def _download(model):
    """Setup-time only: fetch a model into the local cache, telemetry off."""
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    from huggingface_hub import snapshot_download
    print(snapshot_download(model))


if __name__ == "__main__":
    if sys.argv[1:2] == ["--download"]:
        _download(sys.argv[2] if len(sys.argv) > 2 else choose_model()["model"])
    else:
        _worker(sys.argv[1])
