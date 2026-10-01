import json
import os
import socket
import sys
import threading
import types
from pathlib import Path

import pytest

from src import desktop_host


def test_launcher_defers_desktop_import_until_after_freeze_support(monkeypatch):
    import launcher

    events = []
    fake_host = types.ModuleType("src.desktop_host")
    fake_host.main = lambda: events.append("main") or 17
    monkeypatch.setattr(launcher.multiprocessing, "freeze_support", lambda: events.append("freeze"))
    monkeypatch.setitem(sys.modules, "src.desktop_host", fake_host)

    assert launcher.frozen_main() == 17
    assert events == ["freeze", "main"]


def test_importing_launcher_does_not_start_desktop_host():
    import launcher

    assert callable(launcher.frozen_main)


def test_launcher_routes_only_packaged_mcp_child_without_starting_host(tmp_path, monkeypatch):
    import launcher

    internal = tmp_path / "_internal"
    scripts = internal / "mcp_servers"
    scripts.mkdir(parents=True)
    child = scripts / "memory_server.py"
    child.write_text("pass\n", encoding="utf-8")
    observed = []
    monkeypatch.setattr(launcher.sys, "frozen", True, raising=False)
    monkeypatch.setattr(launcher.sys, "_MEIPASS", str(internal), raising=False)
    monkeypatch.setattr(launcher.runpy, "run_path", lambda path, run_name: observed.append((path, run_name)))

    assert launcher._run_frozen_child(["Odysseus.exe", str(child)]) == 0
    assert observed == [(str(child.resolve()), "__main__")]


def test_launcher_rejects_arbitrary_frozen_script_dispatch(tmp_path, monkeypatch):
    import launcher

    internal = tmp_path / "_internal"
    scripts = internal / "mcp_servers"
    scripts.mkdir(parents=True)
    outside = tmp_path / "memory_server.py"
    outside.write_text("raise AssertionError\n", encoding="utf-8")
    monkeypatch.setattr(launcher.sys, "frozen", True, raising=False)
    monkeypatch.setattr(launcher.sys, "_MEIPASS", str(internal), raising=False)

    assert launcher._run_frozen_child(["Odysseus.exe", str(outside)]) is None


def test_desktop_paths_are_persistent_and_separated(tmp_path):
    paths = desktop_host.desktop_paths(local_app_data=str(tmp_path), bundle_root=tmp_path / "bundle")
    assert paths.root == (tmp_path / "Odysseus").resolve()
    assert paths.data.parent == paths.root
    assert paths.logs.parent == paths.root
    assert paths.runtime.parent == paths.root
    assert paths.webview.parent == paths.root
    assert paths.promotion_artifacts.parent == paths.root
    assert paths.trust == paths.root / "config" / "trust"
    assert paths.fixed_webview2 == (tmp_path / "bundle" / "webview2-runtime").resolve()


def test_trusted_desktop_config_is_stable_and_junior_only(tmp_path, monkeypatch):
    paths = desktop_host.desktop_paths(local_app_data=str(tmp_path), bundle_root=tmp_path / "bundle")
    desktop_host.ensure_desktop_directories(paths)
    first = desktop_host.provision_trusted_desktop_config(paths)
    second = desktop_host.provision_trusted_desktop_config(paths)
    assert first == second
    policy_path = Path(first["MOBS_OPERATIONAL_AUTHORITY_FILE"])
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    assert policy["mode"] == "junior"
    assert policy["promotion_result"] == "human_approval_required"
    assert policy["state"] == "active"
    assert Path(first["MOBS_PROMOTION_STORE"]).is_relative_to(paths.root)
    assert not Path(first["MOBS_PROMOTION_STORE"]).is_relative_to(tmp_path / "project")


def test_trusted_desktop_config_refuses_policy_tampering(tmp_path):
    paths = desktop_host.desktop_paths(local_app_data=str(tmp_path), bundle_root=tmp_path / "bundle")
    desktop_host.ensure_desktop_directories(paths)
    env = desktop_host.provision_trusted_desktop_config(paths)
    Path(env["MOBS_OPERATIONAL_AUTHORITY_FILE"]).write_text("{}", encoding="utf-8")
    with pytest.raises(desktop_host.DesktopHostError, match="policy changed"):
        desktop_host.provision_trusted_desktop_config(paths)


def test_reserved_port_has_no_gap_and_ignores_occupied_7000():
    occupied = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        occupied.bind(("127.0.0.1", 7000))
    except OSError:
        occupied.close()
        occupied = None
    if occupied:
        occupied.listen(1)
    listener, port = desktop_host.reserve_loopback_socket()
    try:
        assert listener.getsockname() == ("127.0.0.1", port)
        if occupied:
            assert port != 7000
        with pytest.raises(OSError):
            competing = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                competing.bind(("127.0.0.1", port))
            finally:
                competing.close()
    finally:
        listener.close()
        if occupied:
            occupied.close()


class _FakeKernel:
    def __init__(self):
        self.closed = []

    def CreateMutexW(self, *_args):
        return 42

    def CloseHandle(self, handle):
        self.closed.append(handle)


def test_single_instance_abstraction_rejects_existing_mutex():
    kernel = _FakeKernel()
    guard = desktop_host.WindowsSingleInstance("test", kernel32=kernel,
                                               last_error=lambda: desktop_host._ERROR_ALREADY_EXISTS)
    assert guard.acquire() is False
    assert kernel.closed == [42]


def test_single_instance_abstraction_releases_owned_mutex():
    kernel = _FakeKernel()
    guard = desktop_host.WindowsSingleInstance("test", kernel32=kernel, last_error=lambda: 0)
    assert guard.acquire() is True
    guard.close()
    assert kernel.closed == [42]


def test_readiness_waits_for_explicit_ready():
    responses = iter([(503, b'{"ready":false}'), (200, b'{"ready":true,"checks":{}}')])
    result = desktop_host.wait_for_readiness("http://127.0.0.1/ready", timeout=1,
                                             opener=lambda *_args: next(responses))
    assert result["ready"] is True


def test_readiness_allows_only_the_exact_first_boot_gate():
    result = desktop_host.wait_for_readiness(
        "http://127.0.0.1/ready", timeout=1,
        opener=lambda *_args: (401, b'{"error":"Setup required"}'),
    )
    assert result == {"ready": False, "setup_required": True}


def test_readiness_accepts_public_health_after_internal_integrity_check():
    result = desktop_host.wait_for_readiness(
        "http://127.0.0.1/health", timeout=1,
        opener=lambda *_args: (200, b'{"status":"healthy"}'),
    )
    assert result["status"] == "healthy"


def test_readiness_fails_closed():
    with pytest.raises(desktop_host.DesktopHostError, match="did not become ready"):
        desktop_host.wait_for_readiness(
            "http://127.0.0.1/ready", timeout=0.01,
            opener=lambda *_args: (503, b'{"ready":false,"error":"db"}'),
        )


def test_runtime_integrity_is_checked_without_bypassing_http_auth():
    assert desktop_host.validate_runtime_readiness(
        lambda: {"ready": True, "checks": {"database": {"ok": True}}}
    )["ready"] is True
    with pytest.raises(desktop_host.DesktopHostError, match="integrity checks failed"):
        desktop_host.validate_runtime_readiness(
            lambda: {"ready": False, "checks": {"database": {"ok": False}}}
        )


class _FakeServer:
    def __init__(self):
        self.should_exit = False
        self.force_exit = False
        self.started = threading.Event()

    def run(self, *, sockets):
        self.sockets = sockets
        self.started.set()
        while not self.should_exit:
            self.started.wait(0.01)


def test_backend_controller_shutdown_is_supervised():
    listener, _port = desktop_host.reserve_loopback_socket()
    server = _FakeServer()
    controller = desktop_host.BackendController(object(), listener, server_factory=lambda _app: server)
    try:
        controller.start()
        assert server.started.wait(1)
        controller.stop(timeout=1)
        assert not controller.thread.is_alive()
        assert server.should_exit is True
        assert server.force_exit is False
    finally:
        listener.close()


def test_fixed_runtime_is_mandatory_and_pinned_by_environment(tmp_path, monkeypatch):
    paths = desktop_host.desktop_paths(local_app_data=str(tmp_path), bundle_root=tmp_path / "bundle")
    with pytest.raises(desktop_host.DesktopHostError, match="runtime is missing"):
        desktop_host.ensure_fixed_webview2(paths)
    paths.fixed_webview2.mkdir(parents=True)
    (paths.fixed_webview2 / "msedgewebview2.exe").write_bytes(b"fixture")
    monkeypatch.setattr(desktop_host.platform, "version", lambda: "10.0.22631")
    desktop_host.ensure_fixed_webview2(paths)
    assert os.environ["WEBVIEW2_BROWSER_EXECUTABLE_FOLDER"] == str(paths.fixed_webview2)
    assert os.environ["WEBVIEW2_USER_DATA_FOLDER"] == str(paths.webview)


def test_app_root_distinguishes_source_and_frozen(monkeypatch, tmp_path):
    monkeypatch.delattr(desktop_host.sys, "frozen", raising=False)
    assert desktop_host.app_root() == Path(desktop_host.__file__).resolve().parents[1]
    monkeypatch.setattr(desktop_host.sys, "frozen", True, raising=False)
    monkeypatch.setattr(desktop_host.sys, "_MEIPASS", str(tmp_path), raising=False)
    assert desktop_host.app_root() == tmp_path.resolve()


def test_runtime_state_is_atomic_and_removed(tmp_path):
    paths = desktop_host.desktop_paths(local_app_data=str(tmp_path), bundle_root=tmp_path / "bundle")
    desktop_host.ensure_desktop_directories(paths)
    state = desktop_host.write_runtime_state(paths, 49123)
    payload = json.loads(state.read_text(encoding="utf-8"))
    assert payload == {"format_version": 1, "pid": os.getpid(), "port": 49123}
    assert not list(paths.runtime.glob("*.tmp"))
    desktop_host.clear_runtime_state(state)
    assert not state.exists()
