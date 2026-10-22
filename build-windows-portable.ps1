#Requires -Version 5.1
<# Build the self-contained Windows Desktop MVP as a PyInstaller onedir app. #>
param(
    [string]$Python,
    [string]$WebView2Cab,
    [switch]$CheckOnly
)

$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

function Write-Step($message) { Write-Host ""; Write-Host ("==> " + $message) -ForegroundColor Cyan }
function Fail($message) { Write-Host ""; Write-Host ("ERROR: " + $message) -ForegroundColor Red; exit 1 }

function Assert-BuildTargetsSafe {
    $root = [IO.Path]::GetFullPath($PSScriptRoot).TrimEnd('\')
    foreach ($name in @('build', 'dist')) {
        $target = [IO.Path]::GetFullPath((Join-Path $root $name))
        if ($target -ne "$root\$name") { throw "Build target escapes repository: $target" }
        if (Test-Path -LiteralPath $target) {
            $linked = Get-Item -LiteralPath $target -Force
            if ($linked.Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw "Refusing linked build target: $target"
            }
            # Recursive deletion must not traverse a nested link either.
            if (Get-ChildItem -LiteralPath $target -Recurse -Force -Attributes ReparsePoint -ErrorAction Stop | Select-Object -First 1) {
                throw "Refusing build target containing a reparse point: $target"
            }
        }
    }
    foreach ($process in @(Get-Process -Name 'MOBS Studio' -ErrorAction SilentlyContinue)) {
        $path = $process.Path
        if (-not $path -or $path.StartsWith("$root\dist\", [StringComparison]::OrdinalIgnoreCase)) {
            throw 'Close MOBS Studio normally before building; no process was stopped.'
        }
    }
}

if ($CheckOnly) {
    # No venv creation, pip install, download, extraction, or output cleanup.
    $checkPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $checkPython)) { Fail 'Existing build venv required for CheckOnly.' }
    $dependencyCheck = @'
from importlib.metadata import version, PackageNotFoundError
from pathlib import Path
from packaging.requirements import Requirement
errors = []
for name in ('requirements.txt', 'requirements-desktop.txt'):
    for raw in Path(name).read_text(encoding='utf-8').splitlines():
        line = raw.split('#', 1)[0].strip()
        if not line: continue
        req = Requirement(line)
        if req.marker and not req.marker.evaluate(): continue
        try:
            installed = version(req.name)
            if installed not in req.specifier: errors.append(f'{req.name}: incompatible {installed}')
        except PackageNotFoundError:
            errors.append(f'{req.name}: missing')
if errors: raise SystemExit('\n'.join(errors))
print('Declared build requirements satisfied; nothing installed.')
'@
    & $checkPython -c $dependencyCheck
    if ($LASTEXITCODE -ne 0) { Fail 'Build requirements are not satisfied.' }
    & $checkPython -m pip check
    if ($LASTEXITCODE -ne 0) { Fail 'Dependency consistency check failed.' }
    $checkManifest = Get-Content -LiteralPath '.\desktop\webview2-fixed.json' -Raw | ConvertFrom-Json
    if (-not $WebView2Cab) { $WebView2Cab = Join-Path $env:LOCALAPPDATA "OdysseusBuildCache\WebView2\$($checkManifest.filename)" }
    if (-not (Test-Path -LiteralPath $WebView2Cab)) { Fail 'Pinned WebView2 CAB missing; CheckOnly will not download it.' }
    if ((Get-FileHash -LiteralPath $WebView2Cab -Algorithm SHA256).Hash.ToLowerInvariant() -ne $checkManifest.sha256) { Fail 'WebView2 SHA-256 mismatch.' }
    Write-Host 'Read-only preflight complete; this does not build or certify the installed app.'
    return
}

# Check before dependency installation, then recheck immediately before cleanup.
Assert-BuildTargetsSafe

Write-Step "Selecting Python 3.11+ for the build"
$bootstrapPython = $Python
if (-not $bootstrapPython -and (Test-Path ".\.venv\Scripts\python.exe")) {
    $bootstrapPython = (Resolve-Path ".\.venv\Scripts\python.exe").Path
}
if (-not $bootstrapPython) {
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) { $bootstrapPython = $py.Source }
}
if (-not $bootstrapPython) {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCommand -and $pythonCommand.Source -notlike "*WindowsApps*python.exe") {
        $bootstrapPython = $pythonCommand.Source
    }
}
if (-not $bootstrapPython) { Fail "Python 3.11+ is required to build the package." }

$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    & $bootstrapPython -m venv .venv
    if ($LASTEXITCODE -ne 0) { Fail "Could not create the build virtual environment." }
}

Write-Step "Installing reproducible desktop build dependencies"
& $venvPython -m pip install --disable-pip-version-check -r requirements.txt -r requirements-desktop.txt
if ($LASTEXITCODE -ne 0) { Fail "Dependency installation failed." }

Write-Step "Preparing the pinned WebView2 Fixed Version runtime"
$manifest = Get-Content -LiteralPath ".\desktop\webview2-fixed.json" -Raw | ConvertFrom-Json
$cacheRoot = Join-Path $env:LOCALAPPDATA "OdysseusBuildCache\WebView2"
New-Item -ItemType Directory -Force -Path $cacheRoot | Out-Null
if (-not $WebView2Cab) { $WebView2Cab = Join-Path $cacheRoot $manifest.filename }
if (-not (Test-Path -LiteralPath $WebView2Cab)) {
    Invoke-WebRequest -UseBasicParsing -Uri $manifest.url -OutFile $WebView2Cab
}
$actualHash = (Get-FileHash -LiteralPath $WebView2Cab -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualHash -ne $manifest.sha256) { Fail "WebView2 Fixed Version SHA-256 mismatch." }

Assert-BuildTargetsSafe
foreach ($name in @('build', 'dist')) {
    $target = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot $name))
    if (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target -Recurse -Force }
}
$expandedRoot = Join-Path $PSScriptRoot "build\webview2-expanded"
New-Item -ItemType Directory -Force -Path $expandedRoot | Out-Null
& expand.exe $WebView2Cab -F:* $expandedRoot | Out-Null
if ($LASTEXITCODE -ne 0) { Fail "WebView2 Fixed Version extraction failed." }
$runtimeExe = Get-ChildItem -LiteralPath $expandedRoot -Recurse -Filter "msedgewebview2.exe" | Select-Object -First 1
if (-not $runtimeExe) { Fail "The extracted WebView2 Fixed Version runtime is incomplete." }
$runtimeRoot = $runtimeExe.Directory.FullName

Write-Step "Building MOBS Studio.exe"
$sourceEvidence = Join-Path $PSScriptRoot 'build\source-before.json'
& $venvPython -m src.desktop_package --source $PSScriptRoot --capture-source $sourceEvidence
if ($LASTEXITCODE -ne 0) { Fail 'Could not capture build inputs.' }
$env:ODYSSEUS_WEBVIEW2_FIXED_ROOT = $runtimeRoot
$env:ODYSSEUS_DATA_DIR = Join-Path $PSScriptRoot "build\analysis-data"
$env:ODYSSEUS_INPROCESS_TASKS = "0"
$env:ODYSSEUS_INPROCESS_POLLERS = "0"
& $venvPython -m PyInstaller --noconfirm --clean Odysseus.spec
if ($LASTEXITCODE -ne 0) { Fail "PyInstaller build failed." }

$exe = Join-Path $PSScriptRoot "dist\MOBS Studio\MOBS Studio.exe"
$fixedExe = Join-Path $PSScriptRoot "dist\MOBS Studio\_internal\webview2-runtime\msedgewebview2.exe"
if (-not (Test-Path $exe)) { Fail "MOBS Studio.exe was not produced." }
if (-not (Test-Path $fixedExe)) { Fail "The Fixed Version runtime was not packaged." }

& $venvPython -m src.desktop_package --source $PSScriptRoot --package (Split-Path -Parent $exe) --expected-source $sourceEvidence
if ($LASTEXITCODE -ne 0) { Fail 'Package integrity/source check failed; do not activate this build.' }

Write-Host ""
Write-Host "Desktop MVP build complete: $exe" -ForegroundColor Green
