"""Build-pinned CPython payload for the existing Windows execution boundary.

No environment/PATH override, interpreter discovery, download or execution.
The pin is compiled into the frozen application by its spec, not read from a
mutable sidecar next to the interpreter.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


def inventory_digest(entries: dict[str, str]) -> str:
    return hashlib.sha256(json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def resolve_python() -> tuple[Path, dict | None]:
    from src.windows_native_execution import TrustedExecutionUnavailable, _reparse, inventory

    if not getattr(sys, "frozen", False):
        if sys.prefix != sys.base_prefix:
            # A venv launcher has no adjacent standard library. Its base is
            # supplied by the running interpreter, never discovered in PATH.
            base = Path(sys._base_executable)
            if (not base.is_file() or _reparse(base)
                    or base.parent.resolve() != Path(sys.base_prefix).resolve()):
                raise TrustedExecutionUnavailable("Active Python base runtime is invalid")
            return base, None
        return Path(sys.executable), None
    try:
        from _desktop_python_toolchain_pin import SHA256, VERSION
        bundle = Path(sys._MEIPASS)
        if not bundle.is_absolute() or _reparse(bundle):
            raise ValueError("Invalid bundle root")
        root = bundle / "python-toolchain"
        if _reparse(root) or not root.is_dir():
            raise ValueError("Invalid toolchain root")
        entries = inventory(root, include_git=True)
        if (not isinstance(SHA256, str) or len(SHA256) != 64
                or inventory_digest(entries) != SHA256 or "python.exe" not in entries
                or not isinstance(VERSION, str)):
            raise ValueError("Toolchain does not match build pin")
    except (ImportError, AttributeError, OSError, ValueError, TypeError) as exc:
        raise TrustedExecutionUnavailable("Bundled Python toolchain is unavailable or fails integrity verification") from exc
    return root / "python.exe", {
        "source": "build_pinned_cpython", "version": VERSION,
        "inventory_sha256": SHA256, "executable_sha256": entries["python.exe"],
    }


def verify_staged(source: Path, staged: Path) -> None:
    """Check every staged component against its already verified source."""
    from src.windows_native_execution import TrustedExecutionUnavailable, inventory

    expected = inventory(source, include_git=True)
    actual = inventory(staged, include_git=True)
    if not actual or any(expected.get(name) != digest for name, digest in actual.items()):
        raise TrustedExecutionUnavailable("Python toolchain changed while staging")


def prepare_bundle(destination: Path) -> dict:
    """Build-time only: reuse the existing stager and installed test packages."""
    import importlib.util
    import importlib.metadata
    import shutil
    from src.windows_native_execution import _stage_python_toolchain, _reparse, inventory

    executable = Path(sys._base_executable)
    staged = _stage_python_toolchain(executable, destination)
    root = staged.parent
    licenses = root / "LICENSES"
    licenses.mkdir()
    python_license = executable.parent / "LICENSE.txt"
    if not python_license.is_file() or _reparse(python_license):
        raise RuntimeError("CPython license is unavailable")
    shutil.copy2(python_license, licenses / "CPython.txt")
    site = root / "Lib" / "site-packages"
    site.mkdir()
    for name in ("pytest", "_pytest", "pluggy", "iniconfig", "packaging", "pygments", "colorama"):
        spec = importlib.util.find_spec(name)
        if spec is None or not spec.origin:
            raise RuntimeError(f"Build dependency missing: {name}")
        origin = Path(spec.origin).parent
        # inventory rejects reparse descendants and non-regular files before copy.
        if _reparse(origin):
            raise RuntimeError("Build dependency is a reparse point")
        inventory(origin, include_git=True)
        shutil.copytree(origin, site / name, ignore=shutil.ignore_patterns("__pycache__"))
        distribution = importlib.metadata.distribution("pytest" if name == "_pytest" else name)
        for relative in distribution.files or ():
            if ".dist-info/" not in str(relative).replace("\\", "/"):
                continue
            if relative.name.lower().startswith(("license", "copying")):
                license_file = Path(distribution.locate_file(relative))
                if not license_file.is_file() or _reparse(license_file):
                    raise RuntimeError("Build dependency license is unsafe")
                shutil.copy2(license_file, licenses / f"{name}-{relative.name}")
    spec = importlib.util.find_spec("py")
    if spec and spec.origin:
        origin = Path(spec.origin)
        if _reparse(origin) or origin.name != "py.py":
            raise RuntimeError("Unsupported pytest compatibility dependency")
        shutil.copy2(origin, site / "py.py")
    entries = inventory(root, include_git=True)
    return {"root": root, "sha256": inventory_digest(entries), "version": sys.version.split()[0]}
