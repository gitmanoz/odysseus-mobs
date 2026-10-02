"""Bounded Python diagnostics through the existing mandate and Windows adapter."""
from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

import pytest

from src.mobs_institutional_boot import _command_allowed, _command_tokens, _shell_operation
from src.mobs_mandate_builder import CAPABILITY_PROFILE_VERSION, derive_capabilities
from src.windows_native_execution import (
    WindowsExecutionPolicy, validate_diagnostic_command, inventory,
)


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "project"
    (root / "src").mkdir(parents=True)
    (root / "elsewhere").mkdir()
    (root / "src" / "good.py").write_text("value = 1\n", encoding="utf-8")
    (root / "src" / "second.py").write_text("other = 2\n", encoding="utf-8")
    (root / "src" / "bad.py").write_text("def broken(:\n", encoding="utf-8")
    (root / "src" / "notes.txt").write_text("notes\n", encoding="utf-8")
    (root / "elsewhere" / "outside.py").write_text("outside = 1\n", encoding="utf-8")
    return root


def test_v4_recipes_are_python_only_and_exactly_bounded(project):
    python = derive_capabilities(project, "python")
    assert CAPABILITY_PROFILE_VERSION == python["version"] == "4"
    assert python["allowed_commands"] == [
        "pytest", "python -m pytest", "python -m py_compile", "ruff check --no-fix",
    ]
    assert "python -m py_compile" not in derive_capabilities(project, "generic")["allowed_commands"]
    allowed = tuple(_command_tokens(item, "recipe") for item in python["allowed_commands"])
    assert _command_allowed(("python", "-m", "py_compile", "src/good.py"), allowed)
    assert not _command_allowed(("python", "-m", "compileall", "src"), allowed)
    assert _shell_operation(("python", "-m", "py_compile", "src/good.py")) == "build"


@pytest.mark.parametrize("command", [
    ("python", "-m", "py_compile"),
    ("python", "-m", "py_compile", "src/notes.txt"),
    ("python", "-m", "py_compile", "elsewhere/outside.py"),
    ("python", "-m", "py_compile", "../outside.py"),
    ("python", "-m", "py_compile", "C:/outside.py"),
    ("ruff", "check", "--no-fix", "elsewhere"),
    ("ruff", "check", "--no-fix", "--output-file=output.txt", "src"),
    ("ruff", "check", "--no-fix", "--config", "outside.toml", "src"),
    ("ruff", "check", "--no-fix", "--fix", "src"),
    ("ruff", "check", "--no-fix", "--unknown", "src"),
    ("ruff", "check", "--no-fix", "@src/notes.txt"),
    ("ruff", "format", "src"),
    ("ruff", "--fix", "src"),
])
def test_recipe_rejects_unsafe_arguments(project, command):
    with pytest.raises(ValueError):
        validate_diagnostic_command(command, project, ("src/**",))


def test_recipe_accepts_multiple_python_files_and_ruff_paths(project):
    assert validate_diagnostic_command(
        ("python", "-m", "py_compile", "src/good.py", "src/second.py"),
        project, ("src/**",),
    ) == "python_py_compile"
    assert validate_diagnostic_command(
        ("ruff", "check", "--no-fix", "src"), project, ("src/**",),
    ) == "ruff_check"


def test_recipe_rejects_reparse_path(project):
    link = project / "src" / "linked.py"
    try:
        link.symlink_to(project / "elsewhere" / "outside.py")
    except OSError:
        pytest.skip("Symlink primitive unavailable")
    with pytest.raises(ValueError):
        validate_diagnostic_command(
            ("python", "-m", "py_compile", "src/linked.py"), project, ("src/**",),
        )


def test_ruff_missing_is_factual_unavailability_without_install(project, monkeypatch):
    monkeypatch.setattr("src.windows_native_execution.shutil.which", lambda name: None)
    boundary = WindowsExecutionPolicy(str(project), ("ruff", "check", "--no-fix", "src"),
                                      ("src/**",), (), (), 10)
    result = boundary._execute_sync(threading.Event())
    assert result["exit_code"] == 127
    assert "unavailable: ruff" in result["error"]
    assert result["command_capability"] == {
        "recipe": "ruff_check", "permitted": True,
        "executable_available": False, "boundary_executable": False,
    }


def test_ruff_available_recipe_uses_private_cache_and_existing_boundary(project, monkeypatch):
    import src.windows_native_execution as native

    monkeypatch.setattr(native.shutil, "which", lambda name: sys.executable)

    def stage(executable, private):
        path = private / ".odysseus-toolchain" / "ruff.exe"
        path.parent.mkdir()
        path.write_bytes(b"synthetic executable")
        return path

    def launch(executable, arguments, private, environment, timeout, stop, writes, creates):
        assert arguments == ("check", "--no-fix", "--isolated", "src")
        assert environment["RUFF_CACHE_DIR"].startswith(str(private / ".odysseus-runtime"))
        Path(environment["RUFF_CACHE_DIR"]).mkdir(parents=True)
        (Path(environment["RUFF_CACHE_DIR"]) / "cache.bin").write_bytes(b"cache")
        return {"stdout": "ok", "stderr": "", "exit_code": 0, "timed_out": False,
                "profile_effects": [], "native_configuration": {"synthetic": True}}

    monkeypatch.setattr(native, "_stage_ruff_toolchain", stage)
    monkeypatch.setattr(native, "_run_appcontainer", launch)
    before = inventory(project, include_git=True)
    result = WindowsExecutionPolicy(str(project), ("ruff", "check", "--no-fix", "src"),
                                    ("src/**",), (), (), 10)._execute_sync(threading.Event())
    assert result["exit_code"] == 0
    assert result["trusted_execution"]["command_capability"] == {
        "recipe": "ruff_check", "permitted": True,
        "executable_available": True, "boundary_executable": True,
    }
    assert not result["trusted_execution"]["effects"]
    assert inventory(project, include_git=True) == before


@pytest.mark.skipif(os.name != "nt", reason="Windows Native adapter")
def test_py_compile_diagnostic_keeps_bytecode_private_and_reports_syntax_error(project):
    before = inventory(project, include_git=True)
    policy = lambda *files: WindowsExecutionPolicy(
        str(project), ("python", "-m", "py_compile", *files), ("src/**",), (), (), 30,
    )
    success = policy("src/good.py", "src/second.py")._execute_sync(threading.Event())
    assert success["exit_code"] == 0
    assert success["trusted_execution"]["command_capability"]["recipe"] == "python_py_compile"
    failure = policy("src/bad.py")._execute_sync(threading.Event())
    assert failure["exit_code"] != 0
    assert inventory(project, include_git=True) == before
    assert not list(project.rglob("*.pyc"))
