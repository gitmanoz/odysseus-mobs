"""Explicit message navigation and supervised, noninteractive Windows probes."""
import asyncio
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_message_jump_moves_viewport_and_cancels_following_animation():
    if not shutil.which('node'):
        pytest.skip('Node unavailable')
    source = (ROOT / 'static/js/ui.js').read_text(encoding='utf-8')
    scrolling = source[source.index('let _scrollThrottleTimer ='):source.index('export function autoResize(')].replace('export ', '')
    script = r'''
const assert=require('node:assert/strict');
let cancelled=[],cleared=[],scheduled=[],autoScrollEnabled=true,_scrollRafId=77;
const message={isConnected:true,getBoundingClientRect:()=>({top:300})};
const box={scrollTop:1000,scrollHeight:5000,clientHeight:500,style:{scrollBehavior:'smooth'},contains:m=>m===message,getBoundingClientRect:()=>({top:100})};
let _scrollBox=box;
const document={getElementById:()=>box},window={innerWidth:1200};
const cancelAnimationFrame=id=>cancelled.push(id),clearTimeout=id=>cleared.push(id);
const requestAnimationFrame=fn=>{scheduled.push(fn);return scheduled.length;};
const setTimeout=()=>99;
''' + scrolling + r'''
_scrollThrottleTimer=42;
assert.equal(scrollHistoryToMessage(message),true);
assert.equal(box.scrollTop,1176);
assert.equal(autoScrollEnabled,false);assert.deepEqual(cancelled,[77]);assert.deepEqual(cleared,[42]);
assert.equal(box.style.scrollBehavior,'smooth');
for(let i=0;i<10;i++)scrollHistory();
assert.equal(scheduled.length,0);assert.equal(box.scrollTop,1176);
setAutoScroll(true);
assert.equal(scrollHistoryToMessage({isConnected:true}),false);
assert.equal(autoScrollEnabled,true);
'''
    result = subprocess.run(['node', '-e', script], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr


def test_background_flags_do_not_detach_or_change_posix(monkeypatch):
    from core import platform_compat as platform
    monkeypatch.setattr(platform, 'IS_WINDOWS', False)
    assert platform.background_subprocess_kwargs() == {}
    monkeypatch.setattr(platform, 'IS_WINDOWS', True)
    assert platform.background_subprocess_kwargs() == {'creationflags': 0x08000000}
    assert not platform.background_subprocess_kwargs()['creationflags'] & 0x8


@pytest.mark.skipif(os.name != 'nt', reason='Real Windows console allocation check')
def test_actual_background_child_has_no_console_and_keeps_output():
    from core.platform_compat import background_subprocess_kwargs
    executable = getattr(sys, '_base_executable', sys.executable)
    result = subprocess.run([executable, '-I', '-c', 'import ctypes; print(ctypes.windll.kernel32.GetConsoleWindow())'], capture_output=True, text=True, timeout=15, **background_subprocess_kwargs())
    assert result.returncode == 0
    assert result.stdout.strip() == '0'


def test_git_capture_keeps_hardening_and_hides_windows_console(monkeypatch, tmp_path):
    from core import platform_compat as platform
    from src import mobs_institutional_boot as boot
    original = subprocess.run
    calls = []
    def observed(*args, **kwargs):
        calls.append((args, kwargs))
        return original(*args, **kwargs)
    monkeypatch.setattr(subprocess, 'run', observed)
    assert b'git version' in boot._git(tmp_path, '--version')
    args, options = calls[0]
    assert options['env']['GIT_OPTIONAL_LOCKS'] == '0'
    assert options['env']['GIT_TERMINAL_PROMPT'] == '0'
    assert options['timeout'] == 15
    assert '--no-optional-locks' in args[0]
    if platform.IS_WINDOWS:
        assert options['creationflags'] & 0x08000000


def test_discovery_hardware_and_endpoint_probes_hide_the_console(monkeypatch):
    from core import platform_compat as platform
    from src import model_discovery, endpoint_resolver
    from services.hwfit import hardware
    calls = []
    class Result:
        returncode = 0
        stdout = '{}'
    monkeypatch.setattr(subprocess, 'run', lambda *a, **k: (calls.append(k) or Result()))
    monkeypatch.setattr(platform, 'IS_WINDOWS', True)
    monkeypatch.setattr(model_discovery, '_hosts_cache', [])
    monkeypatch.setattr(model_discovery, '_hosts_cache_time', 0)
    model_discovery.discover_tailscale_hosts()
    monkeypatch.setattr(hardware, '_remote_host', None)
    hardware._run(['local-read-only-probe'])
    monkeypatch.setattr(endpoint_resolver, '_tailscale_cache', {})
    def no_dns(*args):
        raise endpoint_resolver.socket.gaierror('test')
    monkeypatch.setattr(endpoint_resolver.socket, 'getaddrinfo', no_dns)
    endpoint_resolver._resolve_tailscale_host('test-host')
    assert len(calls) == 3
    assert all(call['creationflags'] == 0x08000000 for call in calls)
    assert all(call['capture_output'] and call['timeout'] > 0 for call in calls)


def test_npx_cache_probe_is_hidden_without_automatic_install(monkeypatch):
    from core import platform_compat as platform
    from src import builtin_mcp
    captured = {}
    class Process:
        returncode = 0
        async def communicate(self): return b'1.0.0', b''
    async def launch(*args, **kwargs):
        captured.update(argv=args, options=kwargs)
        return Process()
    monkeypatch.setattr(platform, 'IS_WINDOWS', True)
    monkeypatch.setattr(builtin_mcp, '_is_package_in_npx_cache', lambda _: False)
    monkeypatch.setattr(builtin_mcp.asyncio, 'create_subprocess_exec', launch)
    assert asyncio.run(builtin_mcp._is_npx_package_cached('npx', 'test-package', timeout_s=2))
    assert '--no-install' in captured['argv']
    assert captured['options']['creationflags'] == 0x08000000
