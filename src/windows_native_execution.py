"""Windows-native, fail-closed process boundary for approved MOBS commands.

This is an adapter behind the existing BashTool, not a second tool dispatcher.
Only the private copy of approved project files is exposed to the child. The
original repository is never mounted writable and results are never promoted.
"""
from __future__ import annotations

import asyncio
import ctypes
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path


class TrustedExecutionUnavailable(RuntimeError):
    """The requested boundary cannot make its required guarantees."""


MAX_FILES = 50_000
MAX_FILE_BYTES = 256 * 1024 * 1024
MAX_TOTAL_BYTES = 2 * 1024 * 1024 * 1024
_REPARSE_POINT = 0x400


def _reparse(path: Path) -> bool:
    stat = path.lstat()
    return path.is_symlink() or bool(getattr(stat, "st_file_attributes", 0) & _REPARSE_POINT)


def inventory(root: Path, *, include_git: bool = False) -> dict[str, str]:
    """Hash regular files, including Git-ignored files, without exposing bytes."""
    entries: dict[str, str] = {}
    total = 0
    for directory, dirs, files in os.walk(root, followlinks=False):
        base = Path(directory)
        dirs[:] = sorted(d for d in dirs if include_git or not (base == root and d == ".git"))
        for name in dirs:
            if _reparse(base / name):
                raise TrustedExecutionUnavailable("Reparse directory cannot be inventoried safely")
        for name in sorted(files):
            path = base / name
            if _reparse(path) or not path.is_file():
                raise TrustedExecutionUnavailable("Non-regular project file cannot be inventoried safely")
            before = path.stat()
            if before.st_size > MAX_FILE_BYTES:
                raise TrustedExecutionUnavailable("Project file exceeds inventory limit")
            total += before.st_size
            if len(entries) >= MAX_FILES or total > MAX_TOTAL_BYTES:
                raise TrustedExecutionUnavailable("Project exceeds inventory limit")
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            after = path.stat()
            if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
                raise TrustedExecutionUnavailable("File changed during inventory")
            entries[path.relative_to(root).as_posix()] = digest.hexdigest()
    return entries


def changed_entries(before: dict[str, str], after: dict[str, str]) -> list[dict[str, str]]:
    return [
        {"path": path, "effect": "create" if path not in before else "delete" if path not in after else "write"}
        for path in sorted(before.keys() | after.keys()) if before.get(path) != after.get(path)
    ]


def _apply_private_patch(private: Path, payload: str, read_paths: tuple[str, ...],
                         write_paths: tuple[str, ...], create_paths: tuple[str, ...]) -> None:
    """Apply the existing two-file patch grammar only to the disposable copy."""
    from src.agent_tools.filesystem_tools import _parse_agent_patch, _apply_patch_hunks
    from src.mobs_institutional_boot import _portable_path, _path_is_allowed

    if not isinstance(payload, str) or len(payload.encode("utf-8")) > 131072:
        raise TrustedExecutionUnavailable("Private patch payload is invalid or too large")
    text = payload
    if text.strip().startswith("{"):
        import json
        try:
            args = json.loads(text)
        except (TypeError, ValueError) as exc:
            raise TrustedExecutionUnavailable("Invalid private patch JSON") from exc
        if not isinstance(args, dict):
            raise TrustedExecutionUnavailable("Invalid private patch JSON")
        text = str(args.get("patch_text") or args.get("patchText") or args.get("patch") or "")
    try:
        operations = _parse_agent_patch(text)
    except ValueError as exc:
        raise TrustedExecutionUnavailable(f"Invalid private patch: {exc}") from exc
    if len(operations) != 2:
        raise TrustedExecutionUnavailable("Private patch requires exactly two files")
    paths = [_portable_path(op["path"], "patch path") for op in operations]
    if len({path.casefold() for path in paths}) != 2:
        raise TrustedExecutionUnavailable("Duplicate private patch paths")
    prepared = []
    for op, relative in zip(operations, paths):
        kind = op["kind"]
        if kind not in {"add", "update"}:
            raise TrustedExecutionUnavailable("Private patch permits only create or write")
        path = private / relative
        if not path.resolve().is_relative_to(private.resolve()) or path.is_symlink():
            raise TrustedExecutionUnavailable("Private patch path escapes workspace")
        if kind == "add":
            if path.exists() or not _path_is_allowed(relative, create_paths):
                raise TrustedExecutionUnavailable("Private patch create is not authorized")
            content = op["content"]
        else:
            if (not path.is_file() or not _path_is_allowed(relative, read_paths)
                    or not _path_is_allowed(relative, write_paths)):
                raise TrustedExecutionUnavailable("Private patch write is not authorized")
            try:
                original = path.read_text(encoding="utf-8")
                content = _apply_patch_hunks(original, op["hunks"], relative)
            except (UnicodeError, ValueError) as exc:
                raise TrustedExecutionUnavailable(f"Private patch cannot apply: {exc}") from exc
        prepared.append((path, content))
    for path, content in prepared:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


@dataclass(frozen=True)
class WindowsExecutionPolicy:
    target: str
    command: tuple[str, ...]
    read_paths: tuple[str, ...]
    write_paths: tuple[str, ...]
    create_paths: tuple[str, ...]
    timeout_seconds: int
    promotion_binding: dict | None = None
    private_write: dict | None = None
    private_patch: str | None = None
    validation_artifact: dict | None = None

    async def execute(self) -> dict:
        if os.name != "nt":
            raise TrustedExecutionUnavailable("Windows-native adapter is unavailable on this platform")
        stop = threading.Event()
        task = asyncio.create_task(asyncio.to_thread(self._execute_sync, stop))
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            stop.set()
            try:
                await asyncio.shield(task)
            except Exception:
                pass
            raise

    def _execute_sync(self, stop: threading.Event) -> dict:
        from src.mobs_institutional_boot import _path_is_allowed
        if self.command[0] == "git":
            # A private copy intentionally excludes .git, which can contain
            # credentials and mutable repository state. Do not fake Git output.
            raise TrustedExecutionUnavailable("Git is not available in the private Windows workspace")
        pytest_command = self.command[0] == "pytest"
        try:
            recipe = validate_diagnostic_command(self.command, Path(self.target), self.read_paths)
        except ValueError as exc:
            raise TrustedExecutionUnavailable(str(exc)) from exc
        if pytest_command or self.command[1:3] == ("-m", "pytest"):
            _validate_pytest_arguments(self.command[1:] if pytest_command else self.command[3:],
                                       Path(self.target), self.read_paths)
        executable = (sys.executable if self.command[0] in {"python", "python3", "pytest"}
                      else shutil.which(self.command[0]))
        if not executable or not Path(executable).is_file():
            capability = {"recipe": recipe, "permitted": True,
                          "executable_available": False, "boundary_executable": False}
            return {"error": f"Approved executable is unavailable: {self.command[0]}",
                    "exit_code": 127, "command_capability": capability}
        root = Path(self.target)
        before_target = inventory(root, include_git=True)
        if any(path.startswith(".odysseus-") for path in before_target):
            raise TrustedExecutionUnavailable("Target collides with reserved private adapter paths")
        private = Path(tempfile.mkdtemp(prefix="ody-mobs-native-"))
        try:
            from src.tool_execution import _is_sensitive_path

            for relative in before_target:
                if relative.startswith(".git/"):
                    continue
                if not _path_is_allowed(relative, self.read_paths):
                    continue
                source = root / relative
                if _is_sensitive_path(str(source)):
                    continue
                destination = private / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
            if self.private_patch is not None:
                if self.promotion_binding is None or self.private_write is not None or self.validation_artifact is not None:
                    raise TrustedExecutionUnavailable("Private patch requires one promotion execution")
            elif Path(executable).name.lower() in {"python.exe", "python3.exe"}:
                executable = str(_stage_python_toolchain(Path(executable), private,
                                                         pytest_command or self.command[1:3] == ("-m", "pytest")))
            elif recipe == "ruff_check":
                executable = str(_stage_ruff_toolchain(Path(executable), private))
            else:
                raise TrustedExecutionUnavailable("This first Windows adapter supports only Python commands")
            if inventory(root, include_git=True) != before_target:
                raise TrustedExecutionUnavailable("Target drift while preparing private workspace")
            validated_candidates = []
            if self.validation_artifact is not None:
                from src.mobs_controlled_promotion import _verified_artifact_content, _verified_artifact_contents
                artifact = self.validation_artifact
                if (artifact.get("target_inventory_sha256") != _inventory_digest(before_target)
                        or artifact.get("target_baseline", {}).get("path") != str(root.resolve())):
                    raise TrustedExecutionUnavailable("Validation artifact baseline differs from target")
                from src.mobs_institutional_boot import _portable_path
                multi = artifact.get("format_version") == 2
                effects = artifact["effects"] if multi else [artifact]
                contents = (_verified_artifact_contents(artifact, root) if multi else
                            [_verified_artifact_content(artifact, root)])
                expected_candidate = inventory(private, include_git=True)
                for effect, content in zip(effects, contents):
                    relative = _portable_path(effect["path"], "validation artifact path")
                    if not _path_is_allowed(relative, self.read_paths):
                        raise TrustedExecutionUnavailable("Validation artifact is outside approved read paths")
                    destination = private / relative
                    if (not destination.resolve().is_relative_to(private.resolve())
                            or not destination.parent.is_dir() or destination.is_symlink()):
                        raise TrustedExecutionUnavailable("Validation artifact path is not confined")
                    if effect["effect"] == "write" and before_target.get(relative) != effect["preimage_sha256"]:
                        raise TrustedExecutionUnavailable("Validation preimage differs from target")
                    if effect["effect"] == "create" and relative in before_target:
                        raise TrustedExecutionUnavailable("Validation create destination exists")
                    shutil.copyfile(content, destination)
                    if _file_sha256(destination) != effect["content_sha256"]:
                        raise TrustedExecutionUnavailable("Private validation candidate differs from sealed artifact")
                    expected_candidate[relative] = effect["content_sha256"]
                    validated_candidates.append((destination, effect["content_sha256"]))
                if multi:
                    if inventory(private, include_git=True) != expected_candidate:
                        raise TrustedExecutionUnavailable("Validation candidate has unexpected content")
            (private / ".odysseus-runtime").mkdir()
            before_private = inventory(private, include_git=True)
            environment = _clean_environment(private, Path(executable))
            if recipe == "python_py_compile":
                environment["PYTHONPYCACHEPREFIX"] = str(private / ".odysseus-runtime" / "pycache")
            elif recipe == "ruff_check":
                environment["RUFF_CACHE_DIR"] = str(private / ".odysseus-runtime" / "ruff-cache")
            if self.private_write is not None:
                path = self.private_write.get('path') if isinstance(self.private_write, dict) else None
                content = self.private_write.get('content') if isinstance(self.private_write, dict) else None
                if not isinstance(path, str) or not isinstance(content, str) or len(content.encode('utf-8')) > 65536:
                    raise TrustedExecutionUnavailable('Private write payload is invalid or exceeds the adapter limit')
                encoded = __import__('base64').b64encode(content.encode('utf-8')).decode('ascii')
                arguments = ('-B', '-c', "from pathlib import Path; import base64; Path(%r).write_bytes(base64.b64decode(%r))" % (path, encoded))
            elif pytest_command:
                arguments = ("-B", "-m", "pytest", "-s", "-p", "no:cacheprovider", *self.command[1:],
                             "-o", "log_file=.odysseus-runtime/pytest.log")
            elif self.command[1:3] == ("-m", "pytest"):
                arguments = ("-B", "-m", "pytest", "-s", "-p", "no:cacheprovider", *self.command[3:],
                             "-o", "log_file=.odysseus-runtime/pytest.log")
            elif recipe == "ruff_check":
                arguments = ("check", "--no-fix", "--isolated", *self.command[3:])
            else:
                arguments = ("-B", *self.command[1:])
            if self.private_patch is not None:
                patch_started = time.monotonic()
                _apply_private_patch(private, self.private_patch, self.read_paths,
                                     self.write_paths, self.create_paths)
                if stop.is_set() or time.monotonic() - patch_started > self.timeout_seconds:
                    raise TrustedExecutionUnavailable("Private patch exceeded its cancellation or time limit")
                native = {"stdout": "Private patch prepared", "stderr": "", "exit_code": 0,
                          "timed_out": False, "profile_effects": [],
                          "native_configuration": {"operation": "trusted_private_patch"}}
            else:
                native = _run_appcontainer(
                    executable, arguments, private, environment,
                    self.timeout_seconds, stop, self.write_paths, self.create_paths,
                )
            if self.promotion_binding is not None and native["timed_out"]:
                # A timed-out process can leave an incomplete private state;
                # it must never become a promotable artifact.
                raise TrustedExecutionUnavailable("Timed-out private execution cannot be promoted")
            after_private = inventory(private, include_git=True)
            if any(_file_sha256(path) != digest for path, digest in validated_candidates):
                raise TrustedExecutionUnavailable("Validation command modified the sealed candidate")
            output_files = {".odysseus-stdout", ".odysseus-stderr"}
            all_effects = changed_entries(before_private, after_private)
            adapter_effects = [item for item in all_effects if item["path"] in output_files
                               or item["path"].startswith(".odysseus-runtime/")]
            effects = [item for item in all_effects
                       if item not in adapter_effects and
                       not item["path"].startswith(".odysseus-toolchain/")]
            runtime_effects = [item for item in all_effects
                               if item["path"].startswith(".odysseus-toolchain/")]
            forbidden = [item for item in effects if item["effect"] == "delete" or not _path_is_allowed(
                item["path"], self.create_paths if item["effect"] == "create" else self.write_paths
            )]
            after_target = inventory(root, include_git=True)
            if after_target != before_target:
                raise TrustedExecutionUnavailable("Target workspace drift during private execution")
            if forbidden:
                raise TrustedExecutionUnavailable(
                    "Private command produced effects outside the mandate: "
                    + ", ".join(item["path"] for item in forbidden[:10])
                )
            if (self.validation_artifact is not None
                    and self.validation_artifact.get("format_version") == 2 and effects):
                raise TrustedExecutionUnavailable("Validation changed the sealed two-file candidate workspace")
            promotion_artifact = None
            if self.promotion_binding is not None:
                limit = 2 if self.private_patch is not None else 1
                if len(effects) > limit or any(item['effect'] not in {'create', 'write'} for item in effects):
                    raise TrustedExecutionUnavailable('Promotion-eligible command produced multiple or forbidden effects')
                if self.private_patch is not None and len(effects) != 2:
                    raise TrustedExecutionUnavailable('Private patch did not produce exactly two effects')
                if effects:
                    from src.mobs_controlled_promotion import PromotionError, seal_private_effect, seal_private_effects
                    try:
                        binding = {**self.promotion_binding, 'private_before': before_private,
                                   'target_inventory_sha256': _inventory_digest(before_target)}
                        promotion_artifact = (seal_private_effects(private, effects, binding=binding)
                                              if self.private_patch is not None else
                                              seal_private_effect(private, effects[0], binding=binding))
                    except PromotionError as exc:
                        raise TrustedExecutionUnavailable(str(exc)) from exc
                    if inventory(root, include_git=True) != before_target:
                        raise TrustedExecutionUnavailable(
                            "Target workspace drift during promotion artifact sealing"
                        )
            return {
                "output": native["stdout"] or "(no output)",
                "stderr": native["stderr"],
                "exit_code": native["exit_code"],
                "timed_out": native["timed_out"],
                "trusted_execution": {
                    "adapter": ("windows_private_patch_v1" if self.private_patch is not None
                                else "windows_appcontainer_job_v1"),
                    "guarantees": (["private_project_copy", "private_file_inventory",
                                    "trusted_in_process_patch", "no_child_process"]
                                   if self.private_patch is not None else
                                   ["private_project_copy", "appcontainer_no_network_capability",
                                    "job_tree_termination", "explicit_environment", "private_file_inventory"]),
                    "limitations": ["toolchain_access_is_host_dependent", "git_unavailable_in_private_copy",
                                    "concurrent_same_user_actor_not_cryptographically_attributable"],
                    "command_capability": {"recipe": recipe, "permitted": True,
                                           "executable_available": True,
                                           "boundary_executable": True},
                    "uncertainties": ["OS-brokered effects outside the private workspace and AppContainer profile cannot be attributed"],
                    "effects": effects,
                    "adapter_effects": adapter_effects,
                    "runtime_effects": runtime_effects,
                    "profile_effects": native["profile_effects"],
                    "native_configuration": native.get("native_configuration", {}),
                    "target_before_sha256": _inventory_digest(before_target),
                    "target_after_sha256": _inventory_digest(after_target),
                    "private_before_sha256": _inventory_digest(before_private),
                    "private_after_sha256": _inventory_digest(after_private),
                    "timed_out": native["timed_out"],
                    **({"validated_artifact_digest": self.validation_artifact["artifact_digest"]}
                       if self.validation_artifact is not None else {}),
                    **({"promotion_artifact": promotion_artifact} if promotion_artifact else {}),
                },
            }
        finally:
            shutil.rmtree(private)


def _inventory_digest(entries: dict[str, str]) -> str:
    digest = hashlib.sha256()
    for path, value in sorted(entries.items()):
        digest.update(path.encode("utf-8", "surrogateescape"))
        digest.update(b"\0")
        digest.update(value.encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _validate_pytest_arguments(arguments: tuple[str, ...], root: Path,
                               read_paths: tuple[str, ...]) -> None:
    """Keep pytest's CLI from selecting host paths or injecting configuration."""
    from src.mobs_institutional_boot import _path_is_allowed, _portable_path, _search_root_allowed

    if len(arguments) > 16:
        raise TrustedExecutionUnavailable("Too many pytest arguments for the Windows adapter")
    for arg in arguments:
        if arg in {"-q", "-v", "-x", "-s", "--disable-warnings", "--tb=short", "--tb=line"}:
            continue
        if arg.startswith("--maxfail=") and arg[10:].isdigit() and 1 <= int(arg[10:]) <= 20:
            continue
        if arg.startswith("-"):
            raise TrustedExecutionUnavailable(f"Unsupported pytest option: {arg}")
        try:
            path = _portable_path(arg, "pytest selection")
        except ValueError as exc:
            raise TrustedExecutionUnavailable(str(exc)) from exc
        candidate = (root / path).resolve()
        resolved_root = root.resolve()
        if not candidate.is_relative_to(resolved_root) or not candidate.exists():
            raise TrustedExecutionUnavailable("Pytest selection escapes or is absent from target")
        actual = candidate.relative_to(resolved_root).as_posix()
        if candidate.is_dir():
            allowed = _search_root_allowed(path, read_paths) and _search_root_allowed(actual, read_paths)
        else:
            allowed = _path_is_allowed(path, read_paths) and _path_is_allowed(actual, read_paths)
        if not allowed:
            raise TrustedExecutionUnavailable("Pytest selection is outside approved read paths")


def validate_diagnostic_command(command: tuple[str, ...], root: Path,
                                read_paths: tuple[str, ...]) -> str:
    """Validate the two v4 Python recipes before authorization and again before launch."""
    from src.mobs_institutional_boot import _path_is_allowed, _portable_path, _search_root_allowed
    from src.tool_execution import _is_sensitive_path

    if command[:3] == ("python", "-m", "py_compile"):
        recipe, selections = "python_py_compile", command[3:]
    elif command[:3] == ("ruff", "check", "--no-fix"):
        recipe, selections = "ruff_check", command[3:]
    elif command and command[0] == "ruff":
        raise ValueError("Ruff permits only check --no-fix with approved paths")
    else:
        return "pytest" if command and (command[0] == "pytest" or command[:3] == ("python", "-m", "pytest")) else "legacy"
    if not selections or len(selections) > 16 or sum(len(arg) for arg in selections) > 2048:
        raise ValueError("Diagnostic recipe requires 1–16 bounded project paths")
    resolved_root = root.resolve(strict=True)
    for arg in selections:
        if len(arg) > 240 or arg.startswith("-") or (recipe == "ruff_check" and arg.startswith("@")):
            raise ValueError("Diagnostic recipe does not permit options, argfiles or oversized paths")
        try:
            relative = _portable_path(arg, "diagnostic path")
        except ValueError as exc:
            raise ValueError(str(exc)) from exc
        path = root
        for component in relative.split("/"):
            path = path / component
            if not path.exists() or _reparse(path):
                raise ValueError("Diagnostic path is absent or traverses a reparse point")
        actual = path.resolve(strict=True)
        if not actual.is_relative_to(resolved_root) or _is_sensitive_path(str(actual)):
            raise ValueError("Diagnostic path escapes the authorized project")
        actual_relative = actual.relative_to(resolved_root).as_posix()
        if recipe == "python_py_compile":
            allowed = (path.is_file() and path.suffix.lower() == ".py" and
                       _path_is_allowed(relative, read_paths) and
                       _path_is_allowed(actual_relative, read_paths))
        else:
            allowed = (path.is_file() and _path_is_allowed(relative, read_paths) and
                       _path_is_allowed(actual_relative, read_paths)) if path.is_file() else (
                       path.is_dir() and _search_root_allowed(relative, read_paths) and
                       _search_root_allowed(actual_relative, read_paths))
        if not allowed:
            raise ValueError("Diagnostic path is outside approved read paths or has the wrong type")
    return recipe


def _stage_ruff_toolchain(executable: Path, private: Path) -> Path:
    """Stage an existing Ruff executable; never install or run from host PATH."""
    if _reparse(executable) or executable.suffix.lower() != ".exe":
        raise TrustedExecutionUnavailable("Approved Ruff executable cannot be staged safely")
    destination = private / ".odysseus-toolchain"
    destination.mkdir(exist_ok=True)
    staged = destination / "ruff.exe"
    shutil.copy2(executable, staged)
    if _file_sha256(staged) != _file_sha256(executable):
        raise TrustedExecutionUnavailable("Ruff executable changed while staging")
    return staged


def _stage_python_toolchain(executable: Path, private: Path, include_pytest: bool = False) -> Path:
    """Copy the installed standard runtime, never change host toolchain ACLs."""
    source = executable.parent
    destination = private / ".odysseus-toolchain"
    destination.mkdir()
    for file in source.iterdir():
        if file.is_file() and (file == executable or file.suffix.lower() in {".dll", ".zip"}):
            if _reparse(file):
                raise TrustedExecutionUnavailable("Reparse toolchain component is unsupported")
            shutil.copy2(file, destination / file.name)
    for folder in ("DLLs", "Lib"):
        origin = source / folder
        if not origin.is_dir() or _reparse(origin):
            raise TrustedExecutionUnavailable("Python standard runtime is incomplete")
        for current, dirs, files in os.walk(origin, followlinks=False):
            base = Path(current)
            dirs[:] = sorted(d for d in dirs if d not in {"site-packages", "__pycache__", "ensurepip", "idlelib", "tkinter", "test", "tests"})
            for name in dirs:
                if _reparse(base / name):
                    raise TrustedExecutionUnavailable("Reparse toolchain directory is unsupported")
            for name in files:
                item = base / name
                if _reparse(item) or not item.is_file():
                    raise TrustedExecutionUnavailable("Non-regular toolchain file is unsupported")
                output = destination / folder / item.relative_to(origin)
                output.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, output)
    if include_pytest:
        site = source / "Lib" / "site-packages"
        if not site.is_dir() or _reparse(site):
            raise TrustedExecutionUnavailable("Approved pytest toolchain is unavailable")
        for package in ("pytest", "_pytest", "pluggy", "iniconfig", "packaging", "pygments"):
            origin = site / package
            if not origin.is_dir() or _reparse(origin):
                raise TrustedExecutionUnavailable(f"Approved pytest dependency is unavailable: {package}")
            for current, dirs, files in os.walk(origin, followlinks=False):
                base = Path(current)
                dirs[:] = sorted(d for d in dirs if d != "__pycache__")
                for name in dirs:
                    if _reparse(base / name):
                        raise TrustedExecutionUnavailable("Reparse pytest dependency is unsupported")
                for name in files:
                    item = base / name
                    if _reparse(item) or not item.is_file():
                        raise TrustedExecutionUnavailable("Non-regular pytest dependency is unsupported")
                    output = destination / "Lib" / "site-packages" / package / item.relative_to(origin)
                    output.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, output)
        legacy_py = site / "py.py"
        if legacy_py.is_file() and not _reparse(legacy_py):
            shutil.copy2(legacy_py, destination / "Lib" / "site-packages" / "py.py")
    staged = destination / executable.name
    if not staged.is_file():
        raise TrustedExecutionUnavailable("Python executable could not be staged")
    return staged


def _clean_environment(private: Path, executable: Path) -> dict[str, str]:
    system_root = os.environ.get("SystemRoot") or r"C:\Windows"
    drive = private.drive or Path(system_root).drive
    runtime = private / ".odysseus-runtime"
    return {
        "SystemRoot": system_root,
        "WINDIR": system_root,
        "ComSpec": str(Path(system_root) / "System32" / "cmd.exe"),
        "ProgramData": str(Path(drive + "\\") / "ProgramData"),
        "ALLUSERSPROFILE": str(Path(drive + "\\") / "ProgramData"),
        "PATH": os.pathsep.join((str(executable.parent), str(Path(system_root) / "System32"))),
        "TEMP": str(runtime), "TMP": str(runtime), "USERPROFILE": str(runtime),
        "APPDATA": str(runtime), "LOCALAPPDATA": str(runtime),
        "HOMEDRIVE": drive, "HOMEPATH": str(runtime)[len(drive):],
        "HOME": str(runtime), "PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        "PIP_NO_INDEX": "1",
    }


def _private_acl_rules(private: Path, write_paths: tuple[str, ...],
                       create_paths: tuple[str, ...]) -> list[tuple[Path, str]]:
    """Compile path grants; reject creates that NTFS cannot constrain precisely."""
    from src.mobs_institutional_boot import _path_is_allowed

    rules: list[tuple[Path, str]] = [(private, "(OI)(CI)RX"),
                                     (private / ".odysseus-runtime", "(OI)(CI)M")]
    for file in sorted(private.rglob("*")):
        if not file.is_file() or file.relative_to(private).parts[0].startswith(".odysseus-"):
            continue
        if _path_is_allowed(file.relative_to(private).as_posix(), write_paths):
            rules.append((file, "W"))
    for pattern in create_paths:
        if pattern == "**":
            base = private
        elif pattern.endswith("/**") and "*" not in pattern[:-3] and "?" not in pattern[:-3]:
            base = private / pattern[:-3]
        else:
            raise TrustedExecutionUnavailable("Create path cannot be enforced by directory ACL")
        if not base.is_dir() or base.is_symlink():
            raise TrustedExecutionUnavailable("Create path has no existing private directory")
        # AD/WD permit adding entries but do not grant delete or modify on
        # existing read-only files. CI covers newly created subdirectories.
        rules.append((base, "(CI)(WD,AD)"))
    return rules


def _apply_private_acl(private: Path, sid_text: str, system_root: str,
                       write_paths: tuple[str, ...], create_paths: tuple[str, ...]) -> list[dict[str, str]]:
    icacls = str(Path(system_root) / "System32" / "icacls.exe")
    rules = _private_acl_rules(private, write_paths, create_paths)
    for path, permission in rules:
        args = [icacls, str(path), "/grant", f"*{sid_text}:{permission}"]
        if permission in {"(OI)(CI)RX", "(CI)(WD,AD)"}:
            args.append("/T")
        acl = subprocess.run(args, capture_output=True, timeout=30)
        if acl.returncode:
            raise TrustedExecutionUnavailable("Cannot apply private workspace ACL")
    integrity = subprocess.run([icacls, str(private), "/setintegritylevel", "(OI)(CI)L", "/T"],
                               capture_output=True, timeout=30)
    if integrity.returncode:
        raise TrustedExecutionUnavailable("Cannot apply private workspace integrity level")
    return [{"path": path.relative_to(private).as_posix(), "permission": permission}
            for path, permission in rules]


class _SECURITY_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("nLength", wintypes.DWORD), ("lpSecurityDescriptor", ctypes.c_void_p),
                ("bInheritHandle", wintypes.BOOL)]


class _SECURITY_CAPABILITIES(ctypes.Structure):
    _fields_ = [("AppContainerSid", ctypes.c_void_p), ("Capabilities", ctypes.c_void_p),
                ("CapabilityCount", wintypes.DWORD), ("Reserved", wintypes.DWORD)]


class _STARTUPINFO(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("lpReserved", wintypes.LPWSTR),
                ("lpDesktop", wintypes.LPWSTR), ("lpTitle", wintypes.LPWSTR),
                ("dwX", wintypes.DWORD), ("dwY", wintypes.DWORD),
                ("dwXSize", wintypes.DWORD), ("dwYSize", wintypes.DWORD),
                ("dwXCountChars", wintypes.DWORD), ("dwYCountChars", wintypes.DWORD),
                ("dwFillAttribute", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("wShowWindow", wintypes.WORD), ("cbReserved2", wintypes.WORD),
                ("lpReserved2", ctypes.c_void_p), ("hStdInput", wintypes.HANDLE),
                ("hStdOutput", wintypes.HANDLE), ("hStdError", wintypes.HANDLE)]


class _STARTUPINFOEX(ctypes.Structure):
    _fields_ = [("StartupInfo", _STARTUPINFO), ("lpAttributeList", ctypes.c_void_p)]


class _PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [("hProcess", wintypes.HANDLE), ("hThread", wintypes.HANDLE),
                ("dwProcessId", wintypes.DWORD), ("dwThreadId", wintypes.DWORD)]


class _IO_COUNTERS(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint64) for name in (
        "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
        "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]


class _BASIC_LIMITS(ctypes.Structure):
    _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD)]


class _EXTENDED_LIMITS(ctypes.Structure):
    _fields_ = [("BasicLimitInformation", _BASIC_LIMITS), ("IoInfo", _IO_COUNTERS),
                ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]


def _run_appcontainer(executable: str, arguments: tuple[str, ...], private: Path,
                      environment: dict[str, str], timeout: int, stop: threading.Event,
                      write_paths: tuple[str, ...], create_paths: tuple[str, ...]) -> dict:
    """Launch with stable AppContainer APIs, no network capabilities, and a Job."""
    if os.name != "nt":
        raise TrustedExecutionUnavailable("Windows APIs unavailable")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    userenv = ctypes.WinDLL("userenv", use_last_error=True)
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    ole = ctypes.WinDLL("ole32", use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                   ctypes.POINTER(_SECURITY_ATTRIBUTES), wintypes.DWORD,
                                   wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel.ResumeThread.argtypes = [wintypes.HANDLE]
    kernel.ResumeThread.restype = wintypes.DWORD
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.InitializeProcThreadAttributeList.argtypes = [ctypes.c_void_p, wintypes.DWORD,
                                                         wintypes.DWORD, ctypes.POINTER(ctypes.c_size_t)]
    kernel.UpdateProcThreadAttribute.argtypes = [ctypes.c_void_p, wintypes.DWORD, ctypes.c_size_t,
                                                 ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p,
                                                 ctypes.c_void_p]
    kernel.DeleteProcThreadAttributeList.argtypes = [ctypes.c_void_p]
    advapi.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.LPWSTR)]
    advapi.FreeSid.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    ole.CoTaskMemFree.argtypes = [ctypes.c_void_p]
    name = "OdysseusMobs_" + uuid.uuid4().hex
    sid = ctypes.c_void_p()
    userenv.CreateAppContainerProfile.argtypes = [wintypes.LPCWSTR] * 3 + [ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p)]
    userenv.CreateAppContainerProfile.restype = ctypes.c_long
    userenv.DeleteAppContainerProfile.argtypes = [wintypes.LPCWSTR]
    userenv.DeleteAppContainerProfile.restype = ctypes.c_long
    userenv.GetAppContainerFolderPath.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.LPWSTR)]
    userenv.GetAppContainerFolderPath.restype = ctypes.c_long
    result = userenv.CreateAppContainerProfile(name, name, "Ephemeral MOBS execution", None, 0, ctypes.byref(sid))
    if result != 0:
        raise TrustedExecutionUnavailable(f"Cannot create AppContainer profile: 0x{result & 0xffffffff:08x}")
    handles: list[int] = []
    attributes = None
    job = None
    profile_root = None
    profile_before = {}
    process = _PROCESS_INFORMATION()
    try:
        sid_string = wintypes.LPWSTR()
        if not advapi.ConvertSidToStringSidW(sid, ctypes.byref(sid_string)):
            raise TrustedExecutionUnavailable("Cannot identify AppContainer SID")
        try:
            sid_text = sid_string.value
        finally:
            kernel.LocalFree(sid_string)
        profile_path = wintypes.LPWSTR()
        if userenv.GetAppContainerFolderPath(sid_text, ctypes.byref(profile_path)) != 0:
            raise TrustedExecutionUnavailable("Cannot locate AppContainer profile storage")
        try:
            profile_root = Path(profile_path.value)
        finally:
            ole.CoTaskMemFree(profile_path)
        if profile_root.name.lower() != "ac" or name.lower() not in profile_root.parent.name.lower():
            raise TrustedExecutionUnavailable(
                "Unexpected AppContainer profile storage path component: " + profile_root.name
            )
        if profile_root.exists():
            profile_before = inventory(profile_root)
        acl_rules = _apply_private_acl(private, sid_text, environment["SystemRoot"],
                                       write_paths, create_paths)

        inherit = _SECURITY_ATTRIBUTES(ctypes.sizeof(_SECURITY_ATTRIBUTES), None, True)
        for filename, access, disposition in (("NUL", 0x80000000, 3),
                                              (str(private / ".odysseus-stdout"), 0x40000000, 2),
                                              (str(private / ".odysseus-stderr"), 0x40000000, 2)):
            handle = kernel.CreateFileW(filename, access, 1, ctypes.byref(inherit), disposition, 0x80, None)
            if handle in (None, ctypes.c_void_p(-1).value):
                raise TrustedExecutionUnavailable("Cannot prepare child standard handles")
            handles.append(handle)

        size = ctypes.c_size_t(0)
        kernel.InitializeProcThreadAttributeList(None, 2, 0, ctypes.byref(size))
        attributes = ctypes.create_string_buffer(size.value)
        if not kernel.InitializeProcThreadAttributeList(attributes, 2, 0, ctypes.byref(size)):
            raise TrustedExecutionUnavailable("Cannot initialize process restrictions")
        caps = _SECURITY_CAPABILITIES(sid, None, 0, 0)
        if not kernel.UpdateProcThreadAttribute(attributes, 0, 0x00020009,
                                                ctypes.byref(caps), ctypes.sizeof(caps), None, None):
            raise TrustedExecutionUnavailable("Cannot apply AppContainer identity")
        handle_array = (wintypes.HANDLE * len(handles))(*handles)
        if not kernel.UpdateProcThreadAttribute(attributes, 0, 0x00020002,
                                                ctypes.byref(handle_array), ctypes.sizeof(handle_array), None, None):
            raise TrustedExecutionUnavailable("Cannot restrict inherited handles")
        startup = _STARTUPINFOEX()
        startup.StartupInfo.cb = ctypes.sizeof(startup)
        startup.StartupInfo.dwFlags = 0x00000100  # STARTF_USESTDHANDLES
        startup.StartupInfo.hStdInput, startup.StartupInfo.hStdOutput, startup.StartupInfo.hStdError = handles
        startup.lpAttributeList = ctypes.cast(attributes, ctypes.c_void_p)
        job = kernel.CreateJobObjectW(None, None)
        if not job:
            raise TrustedExecutionUnavailable("Cannot create process Job Object")
        limits = _EXTENDED_LIMITS()
        limits.BasicLimitInformation.LimitFlags = 0x00002000  # KILL_ON_JOB_CLOSE
        if not kernel.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            raise TrustedExecutionUnavailable("Cannot set Job Object kill policy")
        command_line = ctypes.create_unicode_buffer(subprocess.list2cmdline([executable, *arguments]))
        env_block = ctypes.create_unicode_buffer("\0".join(f"{key}={value}" for key, value in sorted(environment.items())) + "\0\0")
        kernel.CreateProcessW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, ctypes.c_void_p,
                                         ctypes.c_void_p, wintypes.BOOL, wintypes.DWORD,
                                         ctypes.c_void_p, wintypes.LPCWSTR, ctypes.c_void_p,
                                         ctypes.POINTER(_PROCESS_INFORMATION)]
        flags = 0x00080000 | 0x00000400 | 0x00000004 | 0x08000000  # extended, unicode env, suspended, no window
        if stop.is_set():
            raise TrustedExecutionUnavailable("Execution cancelled before process launch")
        if not kernel.CreateProcessW(executable, command_line, None, None, True, flags,
                                     env_block, str(private), ctypes.byref(startup), ctypes.byref(process)):
            raise TrustedExecutionUnavailable(f"Cannot launch AppContainer process: {ctypes.get_last_error()}")
        if not kernel.AssignProcessToJobObject(job, process.hProcess):
            kernel.TerminateProcess(process.hProcess, 1)
            raise TrustedExecutionUnavailable("Cannot attach suspended child to process Job Object")
        if kernel.ResumeThread(process.hThread) == 0xffffffff:
            kernel.TerminateJobObject(job, 1)
            raise TrustedExecutionUnavailable("Cannot resume contained process")
        started = time.monotonic()
        timed_out = False
        while True:
            wait = kernel.WaitForSingleObject(process.hProcess, 100)
            if wait == 0:
                break
            if wait != 0x102:
                raise TrustedExecutionUnavailable("Cannot observe contained process")
            if stop.is_set() or time.monotonic() - started >= timeout:
                timed_out = not stop.is_set()
                if not kernel.TerminateJobObject(job, 124 if timed_out else 130):
                    raise TrustedExecutionUnavailable("Cannot terminate controlled process tree")
                if kernel.WaitForSingleObject(process.hProcess, 5000) != 0:
                    raise TrustedExecutionUnavailable("Controlled process did not cease after termination")
                break
        code = wintypes.DWORD()
        if not kernel.GetExitCodeProcess(process.hProcess, ctypes.byref(code)):
            raise TrustedExecutionUnavailable("Cannot capture contained process exit code")
        # No detached descendants are authorized in this slice.
        if not kernel.TerminateJobObject(job, 0):
            raise TrustedExecutionUnavailable("Cannot terminate remaining controlled descendants")
        for handle in handles:
            kernel.CloseHandle(handle)
        handles.clear()
        profile_after = inventory(profile_root) if profile_root.exists() else {}
        return {"exit_code": 124 if timed_out else int(code.value), "timed_out": timed_out,
                "profile_effects": changed_entries(profile_before, profile_after),
                "native_configuration": {"profile": name, "sid": sid_text,
                                         "profile_storage": str(profile_root),
                                         "process_id": int(process.dwProcessId),
                                         "network_capabilities": 0,
                                         "job_kill_on_close": True,
                                         "acl_rules": acl_rules},
                "stdout": (private / ".odysseus-stdout").read_text(encoding="utf-8", errors="replace"),
                "stderr": (private / ".odysseus-stderr").read_text(encoding="utf-8", errors="replace")}
    finally:
        if process.hThread:
            kernel.CloseHandle(process.hThread)
        if process.hProcess:
            kernel.CloseHandle(process.hProcess)
        if job:
            kernel.TerminateJobObject(job, 1)
            kernel.CloseHandle(job)
        for handle in handles:
            kernel.CloseHandle(handle)
        if attributes is not None:
            kernel.DeleteProcThreadAttributeList(attributes)
        advapi.FreeSid(sid)
        if userenv.DeleteAppContainerProfile(name) != 0:
            raise TrustedExecutionUnavailable("Cannot remove ephemeral AppContainer profile")
        if profile_root is not None and profile_root.exists():
            raise TrustedExecutionUnavailable("Ephemeral AppContainer profile storage remains after cleanup")
