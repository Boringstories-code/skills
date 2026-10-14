"""ml_profile.py — the install Profile: schema, validation, load/migrate/write.

One file (`~/.meeting-loop/profile.json` by default, override with
$MEETING_LOOP_PROFILE) holds the answers from `meeting-loop setup`. Every other
command reads it through `load_or_create`. `profile.schema.json` beside this
skill is the single source of truth for its shape; `validate()` is a small
generic JSON-Schema (draft-07 subset) checker, not a separate hand-written
list of rules, so the schema stays the only place behavior is defined.
Stdlib only.
"""
import datetime
import json
import os
import platform
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCHEMA_PATH = HERE.parent / "profile.schema.json"
CURRENT_VERSION = 1

PROTECTED_MARKERS = (
    "/Documents", "/Desktop", "/Library/Mobile Documents",  # iCloud Drive
)


class ProfileError(Exception):
    """A plain-language reason the Profile could not be read or used."""


def schema():
    return json.loads(SCHEMA_PATH.read_text())


def profile_path():
    override = os.environ.get("MEETING_LOOP_PROFILE")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".meeting-loop" / "profile.json"


def _type_ok(value, ty):
    if ty == "object":
        return isinstance(value, dict)
    if ty == "array":
        return isinstance(value, list)
    if ty == "string":
        return isinstance(value, str)
    if ty == "boolean":
        return isinstance(value, bool)
    if ty == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if ty == "null":
        return value is None
    return True


def _matches(instance, condition):
    if not isinstance(instance, dict):
        return False
    for req in condition.get("required", []):
        if req not in instance:
            return False
    for key, sub in condition.get("properties", {}).items():
        if key not in instance:
            continue
        if "const" in sub and instance[key] != sub["const"]:
            return False
        if "enum" in sub and instance[key] not in sub["enum"]:
            return False
    return True


def validate(instance, subschema, path="profile"):
    """-> list of plain-language error strings. Empty list = valid.

    Covers the subset of JSON Schema draft-07 this repo's profile.schema.json
    actually uses: type, required, properties, items, enum, const, allOf with
    if/then. Good enough to be the single checker against the single schema;
    not a general-purpose validator.
    """
    errors = []
    if "const" in subschema and instance != subschema["const"]:
        errors.append(f"{path}: must be {subschema['const']!r}, got {instance!r}")
    if "enum" in subschema and instance not in subschema["enum"]:
        errors.append(f"{path}: must be one of {subschema['enum']}, got {instance!r}")
    ty = subschema.get("type")
    if ty:
        types = ty if isinstance(ty, list) else [ty]
        if not any(_type_ok(instance, t) for t in types):
            errors.append(f"{path}: expected {ty}, got {type(instance).__name__}")
            return errors  # further checks would be noise once the type is wrong
    if isinstance(instance, dict):
        for req in subschema.get("required", []):
            if req not in instance:
                errors.append(f"{path}.{req}: required")
        for key, sub in subschema.get("properties", {}).items():
            if key in instance:
                errors += validate(instance[key], sub, f"{path}.{key}")
        for clause in subschema.get("allOf", []):
            if "if" in clause:
                if _matches(instance, clause["if"]):
                    errors += validate(instance, clause.get("then", {}), path)
            else:
                errors += validate(instance, clause, path)
    elif isinstance(instance, list):
        items = subschema.get("items")
        if items:
            for i, item in enumerate(instance):
                errors += validate(item, items, f"{path}[{i}]")
    return errors


def is_protected(path):
    """True when a Brain root would sit under a macOS-protected location
    (Documents, Desktop, iCloud Drive) where setup or a later run can hit a
    silent permission wall."""
    s = str(Path(path).expanduser())
    return any(marker in s for marker in PROTECTED_MARKERS)


PROTECTED_WARNING = (
    "warning: that folder is inside a macOS-protected location (Documents, Desktop, "
    "or iCloud Drive) — the Terminal or app running meeting-loop may be silently denied "
    "access. Grant it under System Settings -> Privacy & Security -> Files and Folders "
    "(or Full Disk Access) for Terminal / your app, or pick a plain folder instead."
)


def default_profile(brain_root, mics, type_ids, display_name="You"):
    """A minimal, schema-valid Profile for the three setup answers. Every
    other field is a safe, local-only default a user can change by hand."""
    today = datetime.date.today().isoformat()
    os_id = {"Darwin": "darwin-arm64" if platform.machine() == "arm64" else "darwin-x86"}.get(
        platform.system(), "other"
    )
    two_mic = mics == "two"
    return {
        "version": CURRENT_VERSION,
        "install": {
            "id": "default",
            "kind": "person",
            "display_name": display_name,
            "created": today,
            "last_confirmed": today,
        },
        "owner": {"mode": "single", "name": display_name},
        "environment": {
            "os": os_id,
            "ffmpeg": True,
            "asr": {
                "engine": "mlx-whisper",
                "model": "mlx-community/whisper-large-v3-turbo",
                "venv_root": "~/.cache/mlx-whisper-transcribe/venv",
            },
            "hf_allowed": False,
            "diarizer_preference": ["two_mic", "no_hf"] if two_mic else ["no_hf"],
        },
        "brain": {
            "adapter": "plain-folders",
            "root": str(Path(brain_root).expanduser()),
            "capability": "direct-write",
            "frontmatter": False,
            "granularity": "note-per-meeting",
            "merge_policy": "append-dated-block",
        },
        "distillation": {
            "level": "L0",
            "decoupled": True,
            "never_distill": ["raw_audio", "raw_transcript", "private_channels"],
            "cite_back": True,
        },
        "privacy": {
            "destination_shared": False,
            "audience": "solo-sync",
            "consent": {"policy": "self-recorded"},
            "retention": {"raw_audio_days": None, "transcript_days": None, "enforcement": "report-only"},
        },
        "capture": {
            "method": "two-mic" if two_mic else "single-mic-worn",
            "attribution_expectation": "full" if two_mic else "partial",
            "typical_speakers": 2,
        },
        "execution": {"enabled": False},
        "types_registry": "meeting-types.json",
        "decisions": [
            {"id": "D2", "answer": list(type_ids), "asked_on": today, "source": "asked"},
        ],
    }


def _migrate(data):
    """-> (migrated_data, changed:bool). Raises ProfileError when the Profile
    is from a version this build cannot understand."""
    version = data.get("version")
    if version == CURRENT_VERSION:
        return data, False
    if version is not None and (not isinstance(version, int) or version > CURRENT_VERSION):
        raise ProfileError(
            f"this Profile is version {version!r}, newer than this meeting-loop ({CURRENT_VERSION}) "
            "understands; update meeting-loop and try again"
        )
    # version 0 (no version field, e.g. a hand-written or pre-schema Profile):
    # version 1 added the field itself and did not rename or drop anything,
    # so migrating forward is exactly stamping it.
    migrated = dict(data)
    migrated["version"] = CURRENT_VERSION
    return migrated, True


def load_profile(path=None):
    """-> (data, migrated:bool) or raises ProfileError. Does not write."""
    path = Path(path) if path else profile_path()
    try:
        raw = path.read_text()
    except OSError as e:
        raise ProfileError(f"could not read the Profile at {path}: {e}")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ProfileError(f"the Profile at {path} is not valid JSON ({e}); re-run `meeting-loop setup`")
    data, migrated = _migrate(data)
    errors = validate(data, schema())
    if errors:
        raise ProfileError(
            f"the Profile at {path} does not match what meeting-loop expects:\n  "
            + "\n  ".join(errors)
            + "\nre-run `meeting-loop setup` to fix it"
        )
    return data, migrated


def write_profile(data, path=None):
    path = Path(path) if path else profile_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")
    return path
