#Requires -Version 5.1
<# Build the self-contained Windows Desktop MVP as a PyInstaller onedir app. #>
param(
    [string]$Python,
    [string]$WebView2Cab
)

$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

function Write-Step($message) { Write-Host ""; Write-Host ("==> " + $message) -ForegroundColor Cyan }
function Fail($message) { Write-Host ""; Write-Host ("ERROR: " + $message) -ForegroundColor Red; exit 1 }

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

Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue
$expandedRoot = Join-Path $PSScriptRoot "build\webview2-expanded"
New-Item -ItemType Directory -Force -Path $expandedRoot | Out-Null
& expand.exe $WebView2Cab -F:* $expandedRoot | Out-Null
if ($LASTEXITCODE -ne 0) { Fail "WebView2 Fixed Version extraction failed." }
$runtimeExe = Get-ChildItem -LiteralPath $expandedRoot -Recurse -Filter "msedgewebview2.exe" | Select-Object -First 1
if (-not $runtimeExe) { Fail "The extracted WebView2 Fixed Version runtime is incomplete." }
$runtimeRoot = $runtimeExe.Directory.FullName

Write-Step "Building Odysseus.exe"
$env:ODYSSEUS_WEBVIEW2_FIXED_ROOT = $runtimeRoot
$env:ODYSSEUS_DATA_DIR = Join-Path $PSScriptRoot "build\analysis-data"
$env:ODYSSEUS_INPROCESS_TASKS = "0"
$env:ODYSSEUS_INPROCESS_POLLERS = "0"
& $venvPython -m PyInstaller --noconfirm --clean Odysseus.spec
if ($LASTEXITCODE -ne 0) { Fail "PyInstaller build failed." }

$exe = Join-Path $PSScriptRoot "dist\Odysseus\Odysseus.exe"
$fixedExe = Join-Path $PSScriptRoot "dist\Odysseus\_internal\webview2-runtime\msedgewebview2.exe"
if (-not (Test-Path $exe)) { Fail "Odysseus.exe was not produced." }
if (-not (Test-Path $fixedExe)) { Fail "The Fixed Version runtime was not packaged." }

Write-Host ""
Write-Host "Desktop MVP build complete: $exe" -ForegroundColor Green
