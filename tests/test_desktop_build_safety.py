"""Execute only the build guard, with synthetic process and filesystem data."""
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest


@pytest.mark.parametrize('scenario,blocked', [
    ('clear', False), ('open', True), ('unknown', True), ('other', False),
    ('linked', True), ('nested', True), ('unreadable', True)])
def test_build_guard_never_stops_processes_or_crosses_linked_targets(tmp_path, scenario, blocked):
    shell = shutil.which('pwsh') or shutil.which('powershell')
    if not shell: pytest.skip('PowerShell unavailable')
    source = Path(__file__).resolve().parents[1] / 'build-windows-portable.ps1'
    script = r'''
$ErrorActionPreference='Stop'
$ast=[Management.Automation.Language.Parser]::ParseFile($env:GUARD_SOURCE,[ref]$null,[ref]$null)
$f=$ast.Find({param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq 'Assert-BuildTargetsSafe'},$true)
Invoke-Expression ($f.Extent.Text.Replace('$PSScriptRoot', '$env:GUARD_ROOT'))
$PSScriptRoot=$env:GUARD_ROOT
function Stop-Process { throw 'must never stop a process' }
function Get-Process {
 switch($env:GUARD_CASE){
 'open' { [pscustomobject]@{Path="$env:GUARD_ROOT\dist\MOBS Studio\MOBS Studio.exe"} }
 'unknown' { [pscustomobject]@{Path=$null} }
 'other' { [pscustomobject]@{Path='C:\other\MOBS Studio.exe'} }
 }
}
function Test-Path { $true }
function Get-Item {
 if($env:GUARD_CASE -eq 'linked'){[pscustomobject]@{Attributes=[IO.FileAttributes]::ReparsePoint}}
 else{[pscustomobject]@{Attributes=[IO.FileAttributes]::Directory}}
}
function Get-ChildItem {
 if($env:GUARD_CASE -eq 'nested'){[pscustomobject]@{Name='link'}}
 if($env:GUARD_CASE -eq 'unreadable'){throw 'fixture: cannot inspect target'}
}
try { Assert-BuildTargetsSafe; @{blocked=$false}|ConvertTo-Json -Compress }
catch { @{blocked=$true;reason=$_.Exception.Message}|ConvertTo-Json -Compress }
'''
    result = subprocess.run([shell, '-NoProfile', '-NonInteractive', '-Command', script],
        env={**os.environ, 'GUARD_ROOT': str(tmp_path), 'GUARD_SOURCE': str(source), 'GUARD_CASE': scenario},
        capture_output=True, text=True, timeout=30, check=True)
    data = json.loads(result.stdout)
    assert data['blocked'] is blocked, data
    assert 'must never stop' not in data.get('reason', '')
