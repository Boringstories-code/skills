"""brain_writer.py — the only code that writes into the user's Brain.

write_to_brain() enforces the Brain invariants so callers can't get them wrong:
- never overwrite: an existing .md note gets the new text appended as a dated
  block; any other existing file gets a new file created beside it (name-2.ext);
- all or nothing: every file is staged next to its target first, then moved into
  place; if anything fails, the Brain is put back exactly as it was;
- never claim a write you can't make: paths are returned only after the commit;
- never leave the Brain: a path that resolves outside root (`../`, absolute) is refused
  before anything is written. Lexical check, so symlinked folders inside the Brain still work.
"""
import os
from pathlib import Path


class BrainWriteError(Exception):
    """A write into the Brain failed; the Brain is unchanged."""


def write_to_brain(root, writes):
    """writes: [(path relative to root, text)]. Returns the final paths written."""
    root = Path(os.path.normpath(Path(root).expanduser().absolute()))
    for rel, _ in writes:
        target = Path(os.path.normpath(root / rel))
        if target == root or root not in target.parents:
            raise BrainWriteError(f"refusing to write outside the Brain: {rel}")
    plan = []  # (final path, new bytes, old bytes or None when created)
    made_dirs, staged, done = [], [], []
    try:
        for rel, text in writes:
            target = root / rel
            if target.suffix == ".md" and target.exists():
                old = target.read_bytes()
                plan.append((target, old + _gap(old) + text.encode(), old))
            else:
                plan.append((_beside(target), text.encode(), None))
        for final, data, _ in plan:
            made_dirs += _mkdirs(final.parent)
            tmp = final.with_name(f".{final.name}.meeting-loop-tmp")
            staged.append(tmp)
            tmp.write_bytes(data)
        for (final, _, old), tmp in zip(plan, staged):
            os.replace(tmp, final)
            done.append((final, old))
    except OSError as e:
        for tmp in staged:
            tmp.unlink(missing_ok=True)
        for final, old in reversed(done):
            final.write_bytes(old) if old is not None else final.unlink()
        for d in reversed(made_dirs):
            d.rmdir()
        raise BrainWriteError(f"could not write to the Brain at {e.filename or root}: {e.strerror}") from e
    return [final for final, _, _ in plan]


def _gap(old):
    """Blank line between the existing note and the appended block."""
    if not old or old.endswith(b"\n\n"):
        return b""
    return b"\n" if old.endswith(b"\n") else b"\n\n"


def _beside(target):
    n, p = 2, target
    while p.exists():
        p = target.with_name(f"{target.stem}-{n}{target.suffix}")
        n += 1
    return p


def _mkdirs(d):
    """Create d and any missing parents; return the ones created, outermost first."""
    missing = []
    while not d.exists():
        missing.append(d)
        d = d.parent
    for m in reversed(missing):
        m.mkdir()
    return list(reversed(missing))
