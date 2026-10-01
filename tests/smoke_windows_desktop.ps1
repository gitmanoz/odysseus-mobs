#Requires -Version 5.1
<# Real smoke test for the frozen Windows Desktop MVP. #>
param(
    [Parameter(Mandatory = $true)][string]$Executable,
    [Parameter(Mandatory = $true)][string]$LocalAppDataRoot,
    [string]$ReportPath
)

$ErrorActionPreference = "Stop"
$Executable = (Resolve-Path -LiteralPath $Executable).Path
$LocalAppDataRoot = [IO.Path]::GetFullPath($LocalAppDataRoot)
New-Item -ItemType Directory -Force -Path $LocalAppDataRoot | Out-Null

$originalLocalAppData = $env:LOCALAPPDATA
$originalPath = $env:Path
$runtimeState = Join-Path $LocalAppDataRoot "Odysseus\runtime\desktop.json"
$results = [ordered]@{}
$primary = $null
$second = $null
$port7000 = $null
$externalBrowserIdsBefore = @(Get-Process msedge,chrome,firefox -ErrorAction SilentlyContinue |
    Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -ExpandProperty Id)

function Wait-RuntimeState([int]$ProcessId, [int]$Seconds = 120) {
    $deadline = [DateTime]::UtcNow.AddSeconds($Seconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        if (Test-Path -LiteralPath $runtimeState) {
            $state = Get-Content -LiteralPath $runtimeState -Raw | ConvertFrom-Json
            if ($state.pid -eq $ProcessId) { return $state }
        }
        $process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
        if (-not $process) { throw "Desktop process exited before readiness." }
        Start-Sleep -Milliseconds 250
    }
    throw "Desktop runtime state did not appear before timeout."
}

function Wait-DesktopWindow([Diagnostics.Process]$Process) {
    if ($null -eq $Process -or $Process.HasExited) { return }
    $deadline = [DateTime]::UtcNow.AddSeconds(30)
    do {
        $Process.Refresh()
        if ($Process.MainWindowHandle -ne 0) { break }
        Start-Sleep -Milliseconds 200
    } while ([DateTime]::UtcNow -lt $deadline -and -not $Process.HasExited)
    if ($Process.MainWindowHandle -eq 0) { throw "Desktop window did not appear." }
}

function Stop-Desktop([Diagnostics.Process]$Process) {
    if ($null -eq $Process -or $Process.HasExited) { return }
    Wait-DesktopWindow $Process
    if (-not $Process.CloseMainWindow()) {
        throw "Desktop window could not be closed gracefully."
    }
    if (-not $Process.WaitForExit(30000)) {
        throw "Desktop process did not exit after its window closed."
    }
}

try {
    # Keep Windows tools required by the fixed WebView2 runtime, but exclude
    # Python, pip, PowerShell and Docker from the child process PATH.
    $env:LOCALAPPDATA = $LocalAppDataRoot
    $env:Path = "$env:SystemRoot\System32;$env:SystemRoot;$env:SystemRoot\System32\Wbem"
    $results.controlled_path = $env:Path
    $results.python_absent_from_path = -not [bool](Get-Command python -ErrorAction SilentlyContinue)
    $results.docker_absent_from_path = -not [bool](Get-Command docker -ErrorAction SilentlyContinue)

    $port7000 = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, 7000)
    $port7000.Start()
    $results.port_7000_occupied = $true

    $primary = Start-Process -FilePath $Executable -PassThru
    $firstState = Wait-RuntimeState $primary.Id
    Wait-DesktopWindow $primary
    $results.first_pid = $primary.Id
    $results.first_port = [int]$firstState.port
    $results.dynamic_port_avoided_7000 = ([int]$firstState.port -ne 7000)
    $results.desktop_window = ($primary.MainWindowTitle -eq "Odysseus")
    Start-Sleep -Seconds 3
    $buildRoot = [IO.Path]::GetFullPath((Split-Path -Parent $Executable))
    $falseInstanceWindows = @(Get-Process Odysseus -ErrorAction SilentlyContinue | Where-Object {
        $_.MainWindowHandle -ne 0 -and $_.MainWindowTitle -eq "Odysseus could not start" -and
        $_.Path -and [IO.Path]::GetFullPath($_.Path).StartsWith($buildRoot, [StringComparison]::OrdinalIgnoreCase)
    })
    $results.no_false_second_instance_dialogs = ($falseInstanceWindows.Count -eq 0)
    $fixedRoot = [IO.Path]::GetFullPath((Join-Path (Split-Path -Parent $Executable) "_internal\webview2-runtime"))
    $webviewProcesses = @(Get-CimInstance Win32_Process -Filter "Name='msedgewebview2.exe'" -ErrorAction SilentlyContinue)
    $results.fixed_webview2_process = [bool]($webviewProcesses | Where-Object {
        $_.ExecutablePath -and [IO.Path]::GetFullPath($_.ExecutablePath).StartsWith($fixedRoot, [StringComparison]::OrdinalIgnoreCase)
    })
    $externalBrowserIdsAfter = @(Get-Process msedge,chrome,firefox -ErrorAction SilentlyContinue |
        Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -ExpandProperty Id)
    $results.no_external_browser_opened = (@($externalBrowserIdsAfter | Where-Object { $_ -notin $externalBrowserIdsBefore }).Count -eq 0)
    $base = "http://127.0.0.1:$($firstState.port)"
    $results.login_page_http = (Invoke-WebRequest "$base/login" -UseBasicParsing -TimeoutSec 10).StatusCode

    $credentials = @{username="desktop-smoke"; password="Desktop-Smoke-Password-2026!"}
    $setupResponse = Invoke-RestMethod "$base/api/auth/setup" -Method Post -ContentType "application/json" -Body ($credentials | ConvertTo-Json) -TimeoutSec 30
    $results.setup = $setupResponse.ok
    $webSession = New-Object Microsoft.PowerShell.Commands.WebRequestSession
    $loginBody = @{username=$credentials.username; password=$credentials.password; remember=$true} | ConvertTo-Json
    $loginResponse = Invoke-RestMethod "$base/api/auth/login" -Method Post -ContentType "application/json" -Body $loginBody -WebSession $webSession -TimeoutSec 30
    $results.login = $loginResponse.ok
    $results.authenticated_before_restart = (Invoke-RestMethod "$base/api/auth/status" -WebSession $webSession -TimeoutSec 10).authenticated
    $results.ready = (Invoke-RestMethod "$base/api/ready" -WebSession $webSession -TimeoutSec 10).ready
    $chatPage = Invoke-WebRequest "$base/" -UseBasicParsing -WebSession $webSession -TimeoutSec 10
    $results.chat_ui_http = $chatPage.StatusCode
    $results.mobs_read_only_surface_loaded = $chatPage.Content.Contains("mobs-toggle-btn")

    # A fresh Desktop data root starts with no endpoints. Configure one only
    # through the public API used by the existing Models UI, then prove it is
    # selectable and becomes the persisted default for this installation.
    $catalogBefore = Invoke-RestMethod "$base/api/models" -WebSession $webSession -TimeoutSec 10
    $modelsBefore = @($catalogBefore.items)
    $results.clean_install_models_empty = ($modelsBefore.Count -eq 0)
    $endpointForm = @{
        name = "Desktop smoke provider"
        base_url = "http://127.0.0.1:9/v1"
        skip_probe = "true"
        endpoint_kind = "api"
        pinned_models = '["desktop-smoke-model"]'
    }
    $createdEndpoint = Invoke-RestMethod "$base/api/model-endpoints" -Method Post -Body $endpointForm -ContentType "application/x-www-form-urlencoded" -WebSession $webSession -TimeoutSec 30
    $catalogAfter = Invoke-RestMethod "$base/api/models" -WebSession $webSession -TimeoutSec 10
    $modelsAfter = @($catalogAfter.items)
    $results.model_configured_via_existing_api = [bool]($modelsAfter | Where-Object { $_.endpoint_id -eq $createdEndpoint.id -and $_.models -contains "desktop-smoke-model" })
    $defaultAfter = Invoke-RestMethod "$base/api/default-chat" -WebSession $webSession -TimeoutSec 10
    $results.configured_model_is_default = ($defaultAfter.endpoint_id -eq $createdEndpoint.id -and $defaultAfter.model -eq "desktop-smoke-model")

    $second = Start-Process -FilePath $Executable -PassThru
    Start-Sleep -Seconds 2
    $second.Refresh()
    $results.second_instance_refused = (-not $second.HasExited -and $second.MainWindowTitle -eq "Odysseus could not start") -or ($second.HasExited -and $second.ExitCode -eq 2)
    if (-not $second.HasExited) {
        [void]$second.CloseMainWindow()
        [void]$second.WaitForExit(10000)
    }
    $results.second_instance_exit_code = if ($second.HasExited) { $second.ExitCode } else { $null }

    Stop-Desktop $primary
    $results.backend_stopped = $true
    $results.runtime_state_removed = -not (Test-Path -LiteralPath $runtimeState)

    $primary = Start-Process -FilePath $Executable -PassThru
    $secondState = Wait-RuntimeState $primary.Id
    $base2 = "http://127.0.0.1:$($secondState.port)"
    $results.session_persisted_after_restart = (Invoke-RestMethod "$base2/api/auth/status" -WebSession $webSession -TimeoutSec 10).authenticated
    $catalogAfterRestart = Invoke-RestMethod "$base2/api/models" -WebSession $webSession -TimeoutSec 10
    $modelsAfterRestart = @($catalogAfterRestart.items)
    $defaultAfterRestart = Invoke-RestMethod "$base2/api/default-chat" -WebSession $webSession -TimeoutSec 10
    $results.model_persisted_after_restart = [bool]($modelsAfterRestart | Where-Object { $_.endpoint_id -eq $createdEndpoint.id -and $_.models -contains "desktop-smoke-model" })
    $results.default_persisted_after_restart = ($defaultAfterRestart.endpoint_id -eq $createdEndpoint.id -and $defaultAfterRestart.model -eq "desktop-smoke-model")
    $results.webview_profile_created = Test-Path (Join-Path $LocalAppDataRoot "Odysseus\webview")
    $results.promotion_store = Join-Path $LocalAppDataRoot "Odysseus\promotion-artifacts"
    $results.promotion_store_outside_build = -not ([IO.Path]::GetFullPath($results.promotion_store).StartsWith([IO.Path]::GetDirectoryName($Executable), [StringComparison]::OrdinalIgnoreCase))
    Stop-Desktop $primary

    $failed = @($results.GetEnumerator() | Where-Object { $_.Value -eq $false })
    $results.ok = ($failed.Count -eq 0)
}
finally {
    if ($null -ne $second -and -not $second.HasExited) { $second.Kill() }
    if ($null -ne $primary -and -not $primary.HasExited) { $primary.Kill() }
    if ($null -ne $port7000) { $port7000.Stop() }
    $env:LOCALAPPDATA = $originalLocalAppData
    $env:Path = $originalPath
    $json = $results | ConvertTo-Json -Depth 5
    if ($ReportPath) {
        $parent = Split-Path -Parent $ReportPath
        if ($parent) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
        [IO.File]::WriteAllText([IO.Path]::GetFullPath($ReportPath), $json + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))
    }
    Write-Output $json
}

if (-not $results.ok) { exit 1 }
