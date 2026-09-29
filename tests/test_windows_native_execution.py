"""Synthetic P1–P3 subjects defined in TRUSTED_EXECUTION_PROBES.md.

These assertions are software checks and factual evidence, not independent
institutional Pass/Fail verdicts under TEST_EXECUTION_MODEL.md.
"""
from __future__ import annotations

import asyncio
import ctypes
import hashlib
import json
import os
import platform
import sys
import threading
import time
from pathlib import Path

import pytest

from src.windows_native_execution import (
    TrustedExecutionUnavailable, WindowsExecutionPolicy, _validate_pytest_arguments,
    changed_entries, inventory,
)


PROBE_SCRIPT = """from pathlib import Path
import os
import socket
import subprocess
import sys
import time

mode = sys.argv[1]
if mode == 'allowed':
    print(Path('allowed/input.txt').read_text(encoding='utf-8').strip(), flush=True)
elif mode == 'denied_read':
    try:
        print(Path(sys.argv[2]).read_text(encoding='utf-8').strip(), flush=True)
    except OSError:
        print('DENIED', flush=True)
elif mode == 'denied_write':
    try:
        Path(sys.argv[2]).write_text('ESCAPED\\n', encoding='utf-8')
        print('ESCAPED', flush=True)
    except OSError:
        print('DENIED', flush=True)
elif mode == 'env':
    print(os.environ.get('MOBS_PROBE_SENTINEL', 'ABSENT'), flush=True)
elif mode == 'network':
    sock = socket.socket()
    sock.settimeout(2)
    try:
        sock.connect(('127.0.0.1', int(sys.argv[2])))
        print('CONNECTED', flush=True)
    except OSError:
        print('DENIED', flush=True)
    finally:
        sock.close()
elif mode == 'child':
    child = subprocess.Popen([sys.executable, '-I', '-c', 'import time;time.sleep(30)'])
    print(child.pid, flush=True)
    time.sleep(30)
elif mode == 'private_effect':
    Path('allowed/ignored.tmp').write_text('PRIVATE\\n', encoding='utf-8')
    print('WROTE_PRIVATE', flush=True)
elif mode == 'pause':
    Path('allowed/started.flag').write_text('RUNNING\\n', encoding='utf-8')
    time.sleep(2)
    print('DONE', flush=True)
"""
PYTEST_SAMPLE = b"from pathlib import Path\n\ndef test_allowed_sample():\n    assert Path('allowed/input.txt').read_text().strip() == 'ALLOW'\n"


def _record_probe(name: str, facts: dict) -> None:
    """Preserve observations without assigning institutional probe verdicts."""
    destination = os.environ.get("MOBS_PROBE_EVIDENCE_OUTPUT")
    if not destination:
        return
    path = Path(destination)
    evidence = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {
        "protocol": "tests/TRUSTED_EXECUTION_PROBES.md",
        "protocol_sha256": hashlib.sha256((Path(__file__).parent / "TRUSTED_EXECUTION_PROBES.md").read_bytes()).hexdigest(),
        "probe_script_sha256": hashlib.sha256(PROBE_SCRIPT.encode("utf-8")).hexdigest(),
        "python": sys.version, "platform": platform.platform(),
        "observed_at_utc": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "probes": {},
    }
    observed_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
    facts["observed_at_utc"] = observed_at
    evidence["observed_at_utc"] = observed_at
    evidence["probes"][name] = facts
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def _policy_facts(item: WindowsExecutionPolicy, result: dict) -> dict:
    return {"command_tokens": item.command, "target": item.target,
            "read_paths": item.read_paths, "write_paths": item.write_paths,
            "create_paths": item.create_paths, "timeout_seconds": item.timeout_seconds,
            "result": result}


@pytest.fixture
def synthetic(tmp_path: Path):
    target = tmp_path / "target"
    outside = tmp_path / "outside"
    (target / "allowed").mkdir(parents=True)
    outside.mkdir()
    (target / "allowed" / "input.txt").write_bytes(b"ALLOW\n")
    (outside / "denied.txt").write_bytes(b"DENY\n")
    (target / "allowed" / "probe.py").write_bytes(PROBE_SCRIPT.encode("utf-8"))
    assert (target / "allowed" / "probe.py").read_bytes() == PROBE_SCRIPT.encode("utf-8")
    return target, outside


def policy(target: Path, mode: str, *args: str, timeout: int = 10) -> WindowsExecutionPolicy:
    return WindowsExecutionPolicy(
        str(target), (sys.executable, "-I", "allowed/probe.py", mode, *args),
        ("allowed/**",), ("allowed/**",), ("allowed/**",), timeout,
    )


def run(item: WindowsExecutionPolicy) -> dict:
    started = time.monotonic()
    result = asyncio.run(item.execute())
    if os.environ.get("MOBS_PROBE_EVIDENCE_OUTPUT"):
        result["_probe_elapsed_seconds"] = round(time.monotonic() - started, 3)
    return result


def test_governed_bash_stays_in_existing_dispatcher_and_skips_mcp(monkeypatch):
    from src import tool_execution as dispatch
    from src.agent_tools import ToolBlock

    async def forbidden(*args, **kwargs):
        pytest.fail("MCP bash bypassed the trusted adapter")

    class SyntheticBoundary:
        async def execute(self):
            return {"output": "bounded", "exit_code": 0,
                    "trusted_execution": {"adapter": "windows_appcontainer_job_v1"}}

    monkeypatch.setattr(dispatch, "_call_mcp_tool", forbidden)
    monkeypatch.setattr(dispatch, "_owner_is_admin", lambda owner: True)
    _, result = asyncio.run(dispatch.execute_tool_block(
        ToolBlock("bash", "python -m pytest"), trusted_execution=SyntheticBoundary(),
    ))
    assert result["output"] == "bounded"


@pytest.mark.skipif(os.name != "nt", reason="Windows Native adapter")
def test_cancellation_waits_for_adapter_to_stop(monkeypatch):
    started = threading.Event()
    stopped = threading.Event()

    def synthetic_run(self, stop):
        started.set()
        assert stop.wait(5)
        stopped.set()
        return {"exit_code": 130}

    monkeypatch.setattr(WindowsExecutionPolicy, "_execute_sync", synthetic_run)

    async def cancel():
        task = asyncio.create_task(policy(Path("synthetic"), "pause").execute())
        assert await asyncio.to_thread(started.wait, 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(cancel())
    assert stopped.is_set()


def test_pytest_cli_cannot_select_unapproved_paths_or_configuration(synthetic):
    target, _ = synthetic
    _validate_pytest_arguments(("-q", "allowed/probe.py"), target, ("allowed/**",))
    with pytest.raises(TrustedExecutionUnavailable):
        _validate_pytest_arguments(("--rootdir=..",), target, ("allowed/**",))
    with pytest.raises(TrustedExecutionUnavailable):
        _validate_pytest_arguments(("../outside/denied.txt",), target, ("allowed/**",))
    with pytest.raises(TrustedExecutionUnavailable):
        _validate_pytest_arguments(("allowed/probe.py",), target, ("allowed/input.txt",))


@pytest.mark.skipif(os.name != "nt", reason="Windows Native adapter")
def test_git_stays_closed_until_private_repository_support_exists(synthetic):
    target, _ = synthetic
    with pytest.raises(TrustedExecutionUnavailable, match="Git is not available"):
        run(WindowsExecutionPolicy(str(target), ("git", "status"), ("allowed/**",), (), (), 5))


def test_governed_grep_reuses_file_tool_without_spawning_rg(synthetic, monkeypatch):
    from src import tool_execution as dispatch
    from src.agent_tools import ToolBlock
    from src.agent_tools import filesystem_tools

    def forbidden(*args, **kwargs):
        pytest.fail("Governed grep attempted to start an unmanaged process")

    monkeypatch.setattr(filesystem_tools.shutil, "which", forbidden)
    monkeypatch.setattr(dispatch, "_owner_is_admin", lambda owner: True)
    target, _ = synthetic
    _, result = asyncio.run(dispatch.execute_tool_block(
        ToolBlock("grep", '{"pattern":"ALLOW","path":"allowed"}'),
        workspace=str(target), governed_read=True,
    ))
    assert result["exit_code"] == 0
    assert "ALLOW" in result["output"]


def test_governed_read_file_does_not_delegate_to_mcp(synthetic, monkeypatch):
    from src import tool_execution as dispatch
    from src.agent_tools import ToolBlock

    async def forbidden(*args, **kwargs):
        pytest.fail("Governed file read escaped to MCP")

    monkeypatch.setattr(dispatch, "_call_mcp_tool", forbidden)
    monkeypatch.setattr(dispatch, "_owner_is_admin", lambda owner: True)
    target, _ = synthetic
    _, result = asyncio.run(dispatch.execute_tool_block(
        ToolBlock("read_file", "allowed/input.txt"), workspace=str(target), governed_read=True,
    ))
    assert result["exit_code"] == 0
    assert result["output"].strip() == "ALLOW"


def test_inventory_covers_ignored_files_and_rejects_reparse(synthetic):
    target, _ = synthetic
    first = inventory(target)
    (target / "allowed" / "ignored.tmp").write_bytes(b"PRIVATE\n")
    second = inventory(target)
    assert {"path": "allowed/ignored.tmp", "effect": "create"} in changed_entries(first, second)


@pytest.mark.skipif(os.name != "nt", reason="Windows Native adapter")
def test_read_only_file_cannot_be_modified_even_transiently(synthetic):
    target, _ = synthetic
    script = ("from pathlib import Path; p=Path('allowed/input.txt'); "
              "\ntry:\n p.write_text('TEMPORARY')\n print('MUTATED')\n"
              "except OSError:\n print('DENIED')\n")
    result = run(WindowsExecutionPolicy(
        str(target), (sys.executable, "-I", "-c", script),
        ("allowed/**",), (), (), 10,
    ))
    assert result["exit_code"] == 0, result
    assert result["output"].strip() == "DENIED"
    assert (target / "allowed" / "input.txt").read_bytes() == b"ALLOW\n"


@pytest.mark.skipif(os.name != "nt", reason="Windows Native adapter")
def test_create_grant_does_not_modify_existing_read_only_file(synthetic):
    target, _ = synthetic
    script = ("from pathlib import Path; import os; p=Path('allowed/input.txt'); "
              "\ntry:\n p.write_text('TEMPORARY')\n print('MUTATED')\n"
              "except OSError:\n print('DENIED')\n"
              "Path('allowed/new.txt').write_text('NEW'); print('CREATED')\n"
              "try:\n os.replace('allowed/new.txt', p)\n print('REPLACED')\n"
              "except OSError:\n print('REPLACE_DENIED')\n"
              "try:\n p.unlink()\n print('DELETED')\n"
              "except OSError:\n print('DELETE_DENIED')\n")
    result = run(WindowsExecutionPolicy(
        str(target), (sys.executable, "-I", "-c", script),
        ("allowed/**",), (), ("allowed/**",), 10,
    ))
    assert result["exit_code"] == 0, result
    assert result["output"].splitlines() == ["DENIED", "CREATED", "REPLACE_DENIED", "DELETE_DENIED"]
    assert result["trusted_execution"]["effects"] == [{"path": "allowed/new.txt", "effect": "create"}]
    assert (target / "allowed" / "input.txt").read_bytes() == b"ALLOW\n"
    assert not (target / "allowed" / "new.txt").exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows Native adapter")
def test_write_grant_changes_only_approved_private_file(synthetic):
    target, _ = synthetic
    script = ("from pathlib import Path; "
              "Path('allowed/input.txt').write_text('PRIVATE WRITE'); "
              "print(Path('allowed/input.txt').read_text())")
    result = run(WindowsExecutionPolicy(
        str(target), (sys.executable, "-I", "-c", script),
        ("allowed/**",), ("allowed/input.txt",), (), 10,
    ))
    assert result["exit_code"] == 0, result
    assert result["output"].strip() == "PRIVATE WRITE"
    assert result["trusted_execution"]["effects"] == [{"path": "allowed/input.txt", "effect": "write"}]
    assert (target / "allowed" / "input.txt").read_bytes() == b"ALLOW\n"


@pytest.mark.skipif(os.name != "nt", reason="Windows Native adapter")
def test_unenforceable_single_file_create_fails_closed(synthetic):
    target, _ = synthetic
    with pytest.raises(TrustedExecutionUnavailable, match="Create path cannot be enforced"):
        run(WindowsExecutionPolicy(
            str(target), (sys.executable, "-I", "-c", "print('not launched')"),
            ("allowed/**",), (), ("allowed/new.txt",), 10,
        ))


@pytest.mark.skipif(os.name != "nt", reason="Windows Native adapter")
def test_p1_paths_and_python_toolchain(synthetic):
    target, outside = synthetic
    denied = outside / "denied.txt"
    original = hashlib.sha256(denied.read_bytes()).hexdigest()
    allowed_original = hashlib.sha256((target / "allowed" / "input.txt").read_bytes()).hexdigest()
    allowed_policy = policy(target, "allowed")
    denied_read_policy = policy(target, "denied_read", str(denied))
    denied_write_policy = policy(target, "denied_write", str(denied))
    allowed = run(allowed_policy)
    denied_read = run(denied_read_policy)
    denied_write = run(denied_write_policy)
    assert allowed["exit_code"] == 0 and allowed["output"].strip() == "ALLOW"
    assert denied_read["output"].strip() == "DENIED"
    assert denied_write["output"].strip() == "DENIED"
    assert hashlib.sha256(denied.read_bytes()).hexdigest() == original
    assert not (target / "allowed" / "ignored.tmp").exists()
    _record_probe("P1_paths", {
        "outside_file": str(denied), "outside_before_sha256": original,
        "outside_after_sha256": hashlib.sha256(denied.read_bytes()).hexdigest(),
        "allowed_before_sha256": allowed_original,
        "allowed_after_sha256": hashlib.sha256((target / "allowed" / "input.txt").read_bytes()).hexdigest(),
        "target_inventory_after": inventory(target),
        "runs": [_policy_facts(allowed_policy, allowed),
                 _policy_facts(denied_read_policy, denied_read),
                 _policy_facts(denied_write_policy, denied_write)],
    })


@pytest.mark.skipif(os.name != "nt", reason="Windows Native adapter")
def test_p1_pytest_toolchain_sample(synthetic):
    target, _ = synthetic
    sample = target / "allowed" / "test_sample.py"
    sample.write_bytes(PYTEST_SAMPLE)
    assert sample.read_bytes() == PYTEST_SAMPLE
    sample_policy = WindowsExecutionPolicy(
        str(target), ("python", "-m", "pytest", "-q", "allowed/test_sample.py"),
        ("allowed/**",), (), (), 15,
    )
    result = run(sample_policy)
    assert result["exit_code"] == 0, (result["output"], result["stderr"])
    assert "1 passed" in result["output"]
    assert not (target / "allowed" / "__pycache__").exists()
    _record_probe("P1_pytest", {"sample_sha256": hashlib.sha256(PYTEST_SAMPLE).hexdigest(),
                                "run": _policy_facts(sample_policy, result),
                                "target_inventory_after": inventory(target)})


@pytest.mark.skipif(os.name != "nt", reason="Windows Native adapter")
def test_p2_network_environment_and_descendant_timeout(synthetic, monkeypatch):
    import socket
    from src import windows_native_execution as native

    target, _ = synthetic
    original_runner = native._run_appcontainer
    adapter_calls = []

    def observed_runner(executable, arguments, private, environment, timeout, stop,
                        write_paths, create_paths):
        adapter_calls.append({"executable": executable, "arguments": arguments,
                              "private_workspace": str(private), "environment": environment,
                              "timeout_seconds": timeout, "write_paths": write_paths,
                              "create_paths": create_paths})
        return original_runner(executable, arguments, private, environment, timeout, stop,
                               write_paths, create_paths)

    monkeypatch.setattr(native, "_run_appcontainer", observed_runner)
    monkeypatch.setenv("MOBS_PROBE_SENTINEL", "SHOULD_NOT_APPEAR")
    environment_policy = policy(target, "env")
    environment = run(environment_policy)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listener_address = listener.getsockname()
        network_policy = policy(target, "network", str(listener_address[1]))
        network = run(network_policy)
    descendant_policy = policy(target, "child", timeout=2)
    descendant = run(descendant_policy)
    assert environment["output"].strip() == "ABSENT"
    assert network["output"].strip() == "DENIED"
    assert descendant["timed_out"] is True and descendant["exit_code"] == 124
    pid = int(descendant["output"].strip())
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    handle = kernel.OpenProcess(0x00100000, False, pid)
    descendant_observation = {}
    if handle:
        try:
            descendant_observation = {"pid": pid, "wait_result": kernel.WaitForSingleObject(handle, 0)}
            assert descendant_observation["wait_result"] == 0
        finally:
            kernel.CloseHandle(ctypes.c_void_p(handle))
    else:
        # ERROR_INVALID_PARAMETER: the PID has ceased to exist. Other errors
        # would leave descendant state uncertain and must fail this check.
        descendant_observation = {"pid": pid, "open_process_error": ctypes.get_last_error()}
        assert descendant_observation["open_process_error"] == 87
    _record_probe("P2", {"inherited_sentinel_value": "SHOULD_NOT_APPEAR",
                         "listener_address": listener_address,
                         "adapter_calls": adapter_calls,
                         "environment": _policy_facts(environment_policy, environment),
                         "network": _policy_facts(network_policy, network),
                         "descendant": _policy_facts(descendant_policy, descendant),
                         "descendant_observation": descendant_observation,
                         "target_inventory_after": inventory(target)})


@pytest.mark.skipif(os.name != "nt", reason="Windows Native adapter")
def test_p3_private_effect_and_external_drift(synthetic, monkeypatch):
    target, _ = synthetic
    original = inventory(target)
    private_policy = policy(target, "private_effect")
    private_result = run(private_policy)
    assert {"path": "allowed/ignored.tmp", "effect": "create"} in private_result["trusted_execution"]["effects"]
    assert inventory(target) == original
    after_private_effect = inventory(target)

    from src import windows_native_execution as native
    original_runner = native._run_appcontainer
    launch_ready = threading.Event()
    private_path = {}
    observed = {}

    def observed_runner(executable, arguments, private, environment, timeout, stop,
                        write_paths, create_paths):
        private_path['root'] = private
        launch_ready.set()
        observed["command_tokens"] = (executable, *arguments)
        observed["environment"] = environment
        observed["private_path"] = str(private)
        result = original_runner(executable, arguments, private, environment, timeout, stop,
                                 write_paths, create_paths)
        observed["native_result"] = result
        return result

    monkeypatch.setattr(native, '_run_appcontainer', observed_runner)

    writer_errors = []
    drift_observation = {}

    def external_write():
        try:
            assert launch_ready.wait(20)
            marker = private_path['root'] / 'allowed' / 'started.flag'
            deadline = time.monotonic() + 10
            while not marker.exists() and time.monotonic() < deadline:
                time.sleep(0.05)
            assert marker.exists(), 'Private process did not mark its start'
            drift_observation["private_marker_exists"] = True
            drift_observation["private_marker_sha256"] = hashlib.sha256(marker.read_bytes()).hexdigest()
            (target / "allowed" / "input.txt").write_bytes(b"EXTERNAL\n")
            drift_observation["target_after_external_write"] = inventory(target)
        except Exception as exc:
            writer_errors.append(exc)

    writer = threading.Thread(target=external_write)
    writer.start()
    pause_policy = policy(target, "pause")
    pause_started = time.monotonic()
    try:
        with pytest.raises(TrustedExecutionUnavailable, match="drift") as failure:
            run(pause_policy)
    finally:
        writer.join()
    assert not writer_errors, writer_errors
    _record_probe("P3", {"target_inventory_before": original,
                         "private_effect": _policy_facts(private_policy, private_result),
                         "target_inventory_after_private_effect": after_private_effect,
                         "pause_policy": {"command_tokens": pause_policy.command,
                                          "read_paths": pause_policy.read_paths,
                                          "write_paths": pause_policy.write_paths,
                                          "create_paths": pause_policy.create_paths,
                                          "timeout_seconds": pause_policy.timeout_seconds},
                         "adapter_observation": observed,
                         "external_write": drift_observation,
                         "pause_elapsed_seconds": round(time.monotonic() - pause_started, 3),
                         "drift_exception": {"type": type(failure.value).__name__,
                                             "message": str(failure.value)},
                         "target_input_final_bytes_utf8": (target / "allowed" / "input.txt").read_text(encoding="utf-8"),
                         "target_inventory_final": inventory(target)})
