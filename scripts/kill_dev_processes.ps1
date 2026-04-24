param(
    [int[]]$Ports = @(18765, 5173),
    [switch]$DryRun
)

$ErrorActionPreference = "SilentlyContinue"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

function Get-ProcessInfo {
    param([int]$ProcessId)
    Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId"
}

function Is-KokoroDevProcess {
    param($Process)

    if ($null -eq $Process) {
        return $false
    }

    $commandLine = [string]$Process.CommandLine
    if ($commandLine -notlike "*$ProjectRoot*") {
        return $false
    }

    return (
        $commandLine -like "*src.api.server*" -or
        $commandLine -like "*vite*" -or
        $commandLine -like "*frontend:dev*" -or
        $commandLine -like "*tauri:dev*" -or
        $commandLine -like "*concurrently*" -or
        $commandLine -like "*@tauri-apps*"
    )
}

function Stop-KokoroProcess {
    param(
        [int]$ProcessId,
        [string]$Reason
    )

    $process = Get-ProcessInfo -ProcessId $ProcessId
    if ($null -eq $process) {
        Write-Host "[stale] PID $ProcessId not found ($Reason). Windows may still be holding the port."
        return
    }

    if (-not (Is-KokoroDevProcess -Process $process)) {
        Write-Host "[skip] PID $ProcessId $($process.Name) is not recognized as a Kokoro dev process."
        Write-Host "       $($process.CommandLine)"
        return
    }

    Write-Host "[kill] PID $ProcessId $($process.Name) ($Reason)"
    Write-Host "       $($process.CommandLine)"
    if (-not $DryRun) {
        Stop-Process -Id $ProcessId -Force
    }
}

$killed = New-Object System.Collections.Generic.HashSet[int]

foreach ($port in $Ports) {
    $connections = Get-NetTCPConnection -LocalPort $port -State Listen
    if (-not $connections) {
        Write-Host "[free] port $port"
        continue
    }

    foreach ($connection in $connections) {
        $ownerPid = [int]$connection.OwningProcess
        if ($killed.Contains($ownerPid)) {
            continue
        }

        Stop-KokoroProcess -ProcessId $ownerPid -Reason "listening on port $port"
        [void]$killed.Add($ownerPid)
    }
}

$wrapperPatterns = @(
    "*npm run sidecar*",
    "*npm run frontend:dev*",
    "*npm run tauri:dev*",
    "*concurrently*sidecar*",
    "*scripts/start_frontend_dev.js*"
)

$wrappers = Get-CimInstance Win32_Process | Where-Object {
    $commandLine = [string]$_.CommandLine
    if ($commandLine -notlike "*$ProjectRoot*") {
        return $false
    }

    foreach ($pattern in $wrapperPatterns) {
        if ($commandLine -like $pattern) {
            return $true
        }
    }
    return $false
}

foreach ($wrapper in $wrappers) {
    $wrapperPid = [int]$wrapper.ProcessId
    if ($killed.Contains($wrapperPid)) {
        continue
    }

    Stop-KokoroProcess -ProcessId $wrapperPid -Reason "dev wrapper process"
    [void]$killed.Add($wrapperPid)
}

Start-Sleep -Milliseconds 300

foreach ($port in $Ports) {
    $connections = Get-NetTCPConnection -LocalPort $port -State Listen
    if (-not $connections) {
        Write-Host "[ok] port $port is free"
        continue
    }

    foreach ($connection in $connections) {
        Write-Host "[busy] port $port still reports PID $($connection.OwningProcess)"
    }
}
