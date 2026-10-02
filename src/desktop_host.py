"""Thin Windows desktop host for the existing Odysseus web runtime."""
from __future__ import annotations

import ctypes
import hashlib
import json
import logging
import os
import platform
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

APP_NAME = "Odysseus"
POLICY_ID = "odysseus.desktop.junior"
POLICY_VERSION = 2
FIXED_RUNTIME_DIR = "webview2-runtime"
_ERROR_ALREADY_EXISTS = 183


class DesktopHostError(RuntimeError):
    pass


@dataclass(frozen=True)
class DesktopPaths:
    root: Path
    data: Path
    logs: Path
    runtime: Path
    webview: Path
    promotion_artifacts: Path
    config: Path
    trust: Path
    fixed_webview2: Path


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)).resolve()
    return Path(__file__).resolve().parents[1]


def desktop_paths(*, local_app_data: str | None = None, bundle_root: Path | None = None) -> DesktopPaths:
    base = local_app_data or os.environ.get("LOCALAPPDATA")
    if not base:
        raise DesktopHostError("LOCALAPPDATA is unavailable")
    root = (Path(base) / APP_NAME).resolve()
    bundle = (bundle_root or app_root()).resolve()
    return DesktopPaths(
        root=root,
        data=root / "data",
        logs=root / "logs",
        runtime=root / "runtime",
        webview=root / "webview",
        promotion_artifacts=root / "promotion-artifacts",
        config=root / "config",
        trust=root / "config" / "trust",
        fixed_webview2=bundle / FIXED_RUNTIME_DIR,
    )


def ensure_desktop_directories(paths: DesktopPaths) -> None:
    for path in (paths.data, paths.logs, paths.runtime, paths.webview,
                 paths.promotion_artifacts, paths.config, paths.trust):
        path.mkdir(parents=True, exist_ok=True)


def _canonical_json(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def _atomic_create(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())


def provision_trusted_desktop_config(paths: DesktopPaths) -> dict[str, str]:
    """Create or validate installation-pinned Junior policy, fail-closed."""
    installation_file = paths.config / "installation.json"
    if installation_file.exists():
        try:
            installation = json.loads(installation_file.read_text(encoding="utf-8"))
            installation_id = installation["installation_id"]
            uuid.UUID(installation_id)
            if installation != {"format_version": 1, "installation_id": installation_id}:
                raise ValueError
        except (OSError, UnicodeError, json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
            raise DesktopHostError("Desktop installation identity is invalid") from exc
    else:
        installation_id = str(uuid.uuid4())
        _atomic_create(installation_file, _canonical_json({
            "format_version": 1, "installation_id": installation_id,
        }))

    policy = {
        "format_version": 1,
        "id": POLICY_ID,
        "installation_id": installation_id,
        "mode": "junior",
        "promotion_result": "human_approval_required",
        "self_development_promotion_result": "preauthorized",
        "state": "active",
        "version": POLICY_VERSION,
    }
    policy_bytes = _canonical_json(policy)
    policy_file = paths.trust / "operational-authority-junior-v2.json"
    if policy_file.exists():
        try:
            actual = policy_file.read_bytes()
        except OSError as exc:
            raise DesktopHostError("Desktop operational authority policy is unreadable") from exc
        if actual != policy_bytes:
            raise DesktopHostError("Desktop operational authority policy changed")
    else:
        _atomic_create(policy_file, policy_bytes)

    env = {
        "ODYSSEUS_DATA_DIR": str(paths.data),
        "ODYSSEUS_INSTALLATION_ID": installation_id,
        "MOBS_PROMOTION_STORE": str(paths.promotion_artifacts),
        "MOBS_OPERATIONAL_AUTHORITY_FILE": str(policy_file),
        "MOBS_OPERATIONAL_AUTHORITY_SHA256": hashlib.sha256(policy_bytes).hexdigest(),
        "WEBVIEW2_USER_DATA_FOLDER": str(paths.webview),
    }
    os.environ.update(env)
    return env


class WindowsSingleInstance:
    """Named mutex scoped to the current Windows logon session."""

    def __init__(self, identity: str, *, kernel32=None, last_error=None):
        if os.name != "nt" and kernel32 is None:
            raise DesktopHostError("The desktop host requires Windows")
        self._kernel32 = kernel32 or ctypes.WinDLL("kernel32", use_last_error=True)
        if kernel32 is None:
            self._kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
            self._kernel32.CreateMutexW.restype = ctypes.c_void_p
            self._kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
            self._kernel32.CloseHandle.restype = ctypes.c_bool
        self._last_error = last_error or ctypes.get_last_error
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
        self.name = f"Local\\Odysseus-{digest}"
        self.handle = None

    def acquire(self) -> bool:
        handle = self._kernel32.CreateMutexW(None, False, self.name)
        if not handle:
            raise DesktopHostError("Unable to create the single-instance guard")
        if self._last_error() == _ERROR_ALREADY_EXISTS:
            self._kernel32.CloseHandle(handle)
            return False
        self.handle = handle
        return True

    def close(self) -> None:
        if self.handle:
            self._kernel32.CloseHandle(self.handle)
            self.handle = None


def reserve_loopback_socket() -> tuple[socket.socket, int]:
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
        listener.bind(("127.0.0.1", 0))
        listener.listen(128)
        return listener, int(listener.getsockname()[1])
    except Exception:
        listener.close()
        raise


def wait_for_readiness(url: str, *, timeout: float = 90.0,
                       opener: Callable[[str, float], tuple[int, bytes]] | None = None) -> dict:
    def default_open(target: str, request_timeout: float) -> tuple[int, bytes]:
        request = urllib.request.Request(target, headers={"User-Agent": "OdysseusDesktop/1"})
        proxyless = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            with proxyless.open(request, timeout=request_timeout) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read()

    check = opener or default_open
    deadline = time.monotonic() + timeout
    last_error = "backend did not answer"
    while time.monotonic() < deadline:
        try:
            status, body = check(url, min(2.0, max(0.1, deadline - time.monotonic())))
            payload = json.loads(body.decode("utf-8"))
            if status == 200 and payload.get("ready") is True:
                return payload
            if status == 200 and payload.get("status") == "healthy":
                return payload
            # A fresh installation intentionally protects /api/ready until the
            # founder creates the first account. This exact response proves the
            # HTTP runtime is serving and lets the desktop display /login; no
            # other failed readiness result is accepted.
            if status == 401 and payload == {"error": "Setup required"}:
                return {"ready": False, "setup_required": True}
            last_error = payload.get("error") or payload.get("detail") or f"readiness returned HTTP {status}"
        except Exception as exc:
            last_error = str(exc)
        time.sleep(0.15)
    raise DesktopHostError(f"Odysseus backend did not become ready: {last_error}")


def validate_runtime_readiness(checker: Callable[[], dict] | None = None) -> dict:
    """Run the existing integrity probe in-process, outside HTTP auth."""
    if checker is None:
        from src.readiness import check_readiness
        checker = check_readiness
    result = checker()
    if result.get("ready") is not True:
        raise DesktopHostError("Odysseus runtime integrity checks failed")
    return result


class BackendController:
    def __init__(self, application, listener: socket.socket, *, server_factory=None):
        if server_factory is None:
            import uvicorn
            # A windowed PyInstaller executable has no stderr. Reuse the host's
            # file logger instead of Uvicorn's console-oriented log config.
            server_factory = lambda app: uvicorn.Server(uvicorn.Config(
                app, log_level="info", log_config=None, access_log=False,
            ))
        self.listener = listener
        self.server = server_factory(application)
        self.thread = threading.Thread(target=self.server.run, kwargs={"sockets": [listener]},
                                       name="odysseus-backend", daemon=False)

    def start(self) -> None:
        self.thread.start()

    def stop(self, timeout: float = 20.0) -> None:
        self.server.should_exit = True
        if self.thread.is_alive():
            self.thread.join(timeout)
        if self.thread.is_alive():
            self.server.force_exit = True
            self.thread.join(5.0)
        if self.thread.is_alive():
            raise DesktopHostError("Backend did not stop cleanly")


def ensure_fixed_webview2(paths: DesktopPaths) -> None:
    executable = paths.fixed_webview2 / "msedgewebview2.exe"
    if not executable.is_file():
        raise DesktopHostError("The bundled WebView2 Fixed Version runtime is missing")
    os.environ["WEBVIEW2_BROWSER_EXECUTABLE_FOLDER"] = str(paths.fixed_webview2)
    os.environ["WEBVIEW2_USER_DATA_FOLDER"] = str(paths.webview)

    release = platform.version().split(".")
    try:
        build = int(release[2])
    except (IndexError, ValueError):
        build = 0
    if sys.platform == "win32" and build and build < 22000:
        for sid in ("*S-1-15-2-2", "*S-1-15-2-1"):
            completed = subprocess.run(
                ["icacls.exe", str(paths.fixed_webview2), "/grant", f"{sid}:(OI)(CI)(RX)", "/T", "/C"],
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", timeout=120,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if completed.returncode != 0:
                raise DesktopHostError("Unable to secure the bundled WebView2 runtime for Windows 10")


def configure_boot_logging(paths: DesktopPaths) -> Path:
    log_path = paths.logs / "desktop-host.log"
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        handlers=[logging.FileHandler(log_path, encoding="utf-8")], force=True)
    return log_path


def write_runtime_state(paths: DesktopPaths, port: int) -> Path:
    state = paths.runtime / "desktop.json"
    content = _canonical_json({"format_version": 1, "pid": os.getpid(), "port": port})
    temporary = paths.runtime / f"desktop.{os.getpid()}.tmp"
    with temporary.open("wb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, state)
    return state


def clear_runtime_state(state: Path | None) -> None:
    if state is None:
        return
    try:
        state.unlink(missing_ok=True)
    except OSError:
        logging.exception("Could not clear desktop runtime state")


def show_error(message: str) -> None:
    if os.name == "nt":
        ctypes.windll.user32.MessageBoxW(None, message, "Odysseus could not start", 0x10)
    else:
        print(message, file=sys.stderr)


def run_desktop() -> int:
    paths = desktop_paths()
    ensure_desktop_directories(paths)
    log_path = configure_boot_logging(paths)
    guard = WindowsSingleInstance(str(paths.root))
    backend = None
    listener = None
    runtime_state = None
    try:
        if not guard.acquire():
            show_error("Odysseus is already running.")
            return 2
        provision_trusted_desktop_config(paths)
        ensure_fixed_webview2(paths)
        listener, port = reserve_loopback_socket()
        os.environ.update({
            "APP_BIND": "127.0.0.1",
            "APP_PORT": str(port),
            "ODYSSEUS_INTERNAL_BASE": f"http://127.0.0.1:{port}",
        })

        from app import app as fastapi_app
        validate_runtime_readiness()
        backend = BackendController(fastapi_app, listener)
        backend.start()
        wait_for_readiness(f"http://127.0.0.1:{port}/api/health")
        runtime_state = write_runtime_state(paths, port)

        import webview
        webview.create_window("Odysseus", f"http://127.0.0.1:{port}/", width=1440, height=920,
                              min_size=(960, 640), confirm_close=False)
        # No js_api: browser content receives no privileged native bridge.
        webview.start(gui="edgechromium", private_mode=False, storage_path=str(paths.webview))
        return 0
    except Exception as exc:
        logging.exception("Desktop host startup/runtime failure")
        show_error(f"{exc}\n\nStartup log:\n{log_path}")
        return 1
    finally:
        if backend is not None:
            try:
                backend.stop()
            except Exception:
                logging.exception("Backend shutdown failed")
        elif listener is not None:
            listener.close()
        clear_runtime_state(runtime_state)
        guard.close()


def main() -> int:
    if os.name != "nt":
        show_error("Odysseus Desktop MVP supports Windows only.")
        return 1
    return run_desktop()
