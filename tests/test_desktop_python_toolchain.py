"""Frozen admission fails closed; no external executable discovery or launch."""
import sys
from types import SimpleNamespace

import pytest

from src import desktop_python_toolchain as toolchain
from src.windows_native_execution import TrustedExecutionUnavailable, inventory


@pytest.fixture
def frozen(tmp_path, monkeypatch):
    root = tmp_path / "python-toolchain"
    (root / "Lib").mkdir(parents=True)
    (root / "python.exe").write_bytes(b"synthetic interpreter; never executed")
    (root / "Lib" / "os.py").write_text("# synthetic\n")
    pin = SimpleNamespace(SHA256=toolchain.inventory_digest(inventory(root, include_git=True)), VERSION="fixture")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    monkeypatch.setitem(sys.modules, "_desktop_python_toolchain_pin", pin)
    return root, pin


def test_frozen_uses_only_build_pinned_interpreter(frozen, monkeypatch):
    root, pin = frozen
    monkeypatch.setenv("PATH", "C:/untrusted")
    monkeypatch.setenv("PYTHONHOME", "C:/untrusted")
    monkeypatch.setattr(sys, "executable", "C:/Studio/MOBS Studio.exe")
    executable, provenance = toolchain.resolve_python()
    assert executable == root / "python.exe"
    assert provenance["inventory_sha256"] == pin.SHA256
    assert provenance["source"] == "build_pinned_cpython"


@pytest.mark.parametrize("mutation", ["executable", "stdlib", "extra", "missing", "pin"])
def test_frozen_integrity_failures_block(frozen, mutation):
    root, pin = frozen
    if mutation == "executable":
        (root / "python.exe").write_bytes(b"changed")
    elif mutation == "stdlib":
        (root / "Lib" / "os.py").write_text("changed")
    elif mutation == "extra":
        (root / "Lib" / "sitecustomize.py").write_text("raise Exception()")
    elif mutation == "missing":
        (root / "python.exe").unlink()
    else:
        pin.SHA256 = "0" * 64
    with pytest.raises(TrustedExecutionUnavailable):
        toolchain.resolve_python()


def test_frozen_without_compiled_pin_never_falls_back(frozen, monkeypatch):
    monkeypatch.setitem(sys.modules, "_desktop_python_toolchain_pin", None)
    with pytest.raises(TrustedExecutionUnavailable):
        toolchain.resolve_python()


def test_reparse_toolchain_rejected(frozen, monkeypatch):
    import src.windows_native_execution as native
    root, _ = frozen
    original = native._reparse
    monkeypatch.setattr(native, "_reparse", lambda path: path == root or original(path))
    with pytest.raises(TrustedExecutionUnavailable):
        toolchain.resolve_python()


def test_private_staging_tamper_rejected(frozen, tmp_path):
    import shutil
    root, _ = frozen
    private = tmp_path / "private"
    shutil.copytree(root, private)
    toolchain.verify_staged(root, private)
    (private / "python.exe").write_bytes(b"tampered")
    with pytest.raises(TrustedExecutionUnavailable):
        toolchain.verify_staged(root, private)


def test_source_execution_preserves_existing_selection(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.setattr(sys, "prefix", sys.base_prefix)
    executable, provenance = toolchain.resolve_python()
    assert str(executable) == sys.executable
    assert provenance is None


def test_source_venv_resolves_active_base_without_path_discovery(tmp_path, monkeypatch):
    base = tmp_path / "base"
    base.mkdir()
    (base / "python.exe").write_bytes(b"fixture; never executed")
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.setattr(sys, "prefix", str(tmp_path / "venv"))
    monkeypatch.setattr(sys, "base_prefix", str(base))
    monkeypatch.setattr(sys, "_base_executable", str(base / "python.exe"))
    monkeypatch.setenv("PATH", "C:/untrusted")
    executable, _ = toolchain.resolve_python()
    assert executable == base / "python.exe"
    monkeypatch.setattr(sys, "_base_executable", str(tmp_path / "other/python.exe"))
    with pytest.raises(TrustedExecutionUnavailable):
        toolchain.resolve_python()
