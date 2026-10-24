"""Tests for ``core.atomic_io`` durability and crash-safety behavior.

``core.atomic_io`` provides ``atomic_write_json`` and ``atomic_write_text``.
Both write to a sibling ``.tmp.<pid>`` file, ``fsync`` it, then ``os.replace``
into place so a crash mid-write leaves the previous good copy untouched rather
than a truncated/empty file.

These tests cover the happy path (round-trip, indent, parent-dir creation,
full overwrite, no leftover tmp) and the two failure paths the implementation
guarantees: the target file is preserved when serialization fails before the
replace, and when ``os.replace`` itself fails.
"""
import importlib.util
import json
from pathlib import Path

import pytest

# Load core/atomic_io.py directly by file path so this stays a pure unit test:
# importing the ``core`` package would pull in core/__init__.py and the
# database/session modules, making the test depend on data/app.db existing.
ROOT = Path(__file__).resolve().parents[1]
ATOMIC_IO_PATH = ROOT / "core" / "atomic_io.py"
_spec = importlib.util.spec_from_file_location("_atomic_io_under_test", ATOMIC_IO_PATH)
atomic_io = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(atomic_io)

atomic_write_json = atomic_io.atomic_write_json
atomic_write_text = atomic_io.atomic_write_text


def _tmp_siblings(directory: Path, name: str) -> list:
    """Return any ``<name>.tmp.*`` files the helpers may have left behind."""
    return list(directory.glob(f"{name}.tmp.*"))


# ---------------------------------------------------------------------------
# atomic_write_json — happy path.
# ---------------------------------------------------------------------------
def test_atomic_write_json_round_trips_object(tmp_path):
    target = tmp_path / "data.json"
    original = {"a": 1, "b": [1, 2, 3], "c": {"nested": True}, "s": "héllo"}

    atomic_write_json(str(target), original)

    assert json.loads(target.read_text(encoding="utf-8")) == original


def test_atomic_write_json_honors_indent(tmp_path):
    target = tmp_path / "indented.json"

    atomic_write_json(str(target), {"a": 1}, indent=2)

    text = target.read_text(encoding="utf-8")
    assert "\n" in text
    assert text == json.dumps({"a": 1}, indent=2)


def test_atomic_write_json_creates_missing_parent_dirs(tmp_path):
    target = tmp_path / "deep" / "nested" / "data.json"

    atomic_write_json(str(target), {"ok": True})

    assert target.exists()
    assert json.loads(target.read_text(encoding="utf-8")) == {"ok": True}


def test_atomic_write_json_fully_overwrites_longer_content(tmp_path):
    target = tmp_path / "data.json"
    atomic_write_json(str(target), {"k": "x" * 500})

    atomic_write_json(str(target), {"k": "short"})

    assert json.loads(target.read_text(encoding="utf-8")) == {"k": "short"}
    # No trailing bytes from the previous, longer write.
    assert target.read_text(encoding="utf-8") == json.dumps({"k": "short"})


def test_atomic_write_json_leaves_no_tmp_file(tmp_path):
    target = tmp_path / "data.json"

    atomic_write_json(str(target), {"a": 1})

    assert _tmp_siblings(tmp_path, "data.json") == []


# ---------------------------------------------------------------------------
# atomic_write_json — failure path: target preserved on serialization error.
# ---------------------------------------------------------------------------
def test_atomic_write_json_preserves_target_when_serialization_fails(tmp_path):
    target = tmp_path / "data.json"
    atomic_write_json(str(target), {"existing": "value"})
    before = target.read_text(encoding="utf-8")

    # A set is not JSON-serializable, so json.dump raises after the tmp file
    # is opened but before os.replace runs.
    with pytest.raises(TypeError):
        atomic_write_json(str(target), {"bad": {1, 2, 3}})

    assert target.read_text(encoding="utf-8") == before


# ---------------------------------------------------------------------------
# atomic_write_text — happy path.
# ---------------------------------------------------------------------------
def test_atomic_write_text_round_trips(tmp_path):
    target = tmp_path / "note.txt"
    text = "line one\nline two\nunicode: héllo\n"

    atomic_write_text(str(target), text)

    assert target.read_text(encoding="utf-8") == text


def test_atomic_write_text_creates_missing_parent_dirs(tmp_path):
    target = tmp_path / "deep" / "nested" / "note.txt"

    atomic_write_text(str(target), "content")

    assert target.exists()
    assert target.read_text(encoding="utf-8") == "content"


def test_atomic_write_text_fully_overwrites_longer_content(tmp_path):
    target = tmp_path / "note.txt"
    atomic_write_text(str(target), "x" * 500)

    atomic_write_text(str(target), "short")

    assert target.read_text(encoding="utf-8") == "short"


def test_atomic_write_text_leaves_no_tmp_file(tmp_path):
    target = tmp_path / "note.txt"

    atomic_write_text(str(target), "content")

    assert _tmp_siblings(tmp_path, "note.txt") == []


def test_atomic_write_text_rejects_non_string_before_tmp_file(tmp_path):
    target = tmp_path / "note.txt"

    with pytest.raises(TypeError):
        atomic_write_text(str(target), 123)

    assert not target.exists()
    assert _tmp_siblings(tmp_path, "note.txt") == []


# ---------------------------------------------------------------------------
# atomic_write_text — failure path: target preserved when replace fails.
# ---------------------------------------------------------------------------
def test_atomic_write_text_preserves_target_when_replace_fails(tmp_path, monkeypatch):
    target = tmp_path / "note.txt"
    atomic_write_text(str(target), "original content")
    before = target.read_text(encoding="utf-8")

    def boom(src, dst):
        raise OSError("replace failed")

    monkeypatch.setattr(atomic_io.os, "replace", boom)

    with pytest.raises(OSError):
        atomic_write_text(str(target), "new content that never lands")

    assert target.read_text(encoding="utf-8") == before


@pytest.mark.parametrize("winerror", [5, 32])
@pytest.mark.parametrize("writer,value", [(atomic_write_json, {"new": True}), (atomic_write_text, "new")])
def test_windows_transient_share_conflict_retries_atomic_replace(tmp_path, monkeypatch, winerror, writer, value):
    target = tmp_path / "persisted"
    real_replace = atomic_io.os.replace
    calls = []
    delays = []

    def briefly_blocked(source, destination):
        calls.append((source, destination))
        if len(calls) < 3:
            error = PermissionError("fixture sharing conflict")
            error.winerror = winerror
            raise error
        return real_replace(source, destination)

    monkeypatch.setattr(atomic_io.os, "replace", briefly_blocked)
    monkeypatch.setattr(atomic_io.time, "sleep", delays.append)
    writer(str(target), value)
    assert len(calls) == 3
    assert delays == [0.025, 0.05]
    assert target.read_text(encoding="utf-8") == (json.dumps(value) if isinstance(value, dict) else value)


def test_windows_permanent_denial_is_bounded_and_preserves_destination(tmp_path, monkeypatch):
    target = tmp_path / "persisted"
    atomic_write_json(str(target), {"old": True})
    attempts = []
    delays = []

    def denied(*_):
        attempts.append(1)
        error = PermissionError("fixture permanent denial")
        error.winerror = 5
        raise error

    monkeypatch.setattr(atomic_io.os, "replace", denied)
    monkeypatch.setattr(atomic_io.time, "sleep", delays.append)
    with pytest.raises(PermissionError):
        atomic_write_json(str(target), {"new": True})
    assert len(attempts) == 5
    assert delays == [0.025, 0.05, 0.1, 0.2]
    assert json.loads(target.read_text(encoding="utf-8")) == {"old": True}
