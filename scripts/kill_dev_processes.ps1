param(
    [int[]]$Ports = @(18765, 5173),
    [switch]$DryRun
)

$ErrorActionPreference = "SilentlyContinue"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

function Contains-ProjectRoot {
    param([string]$CommandLine)
    return $CommandLine.IndexOf($ProjectRoot, [StringComparison]::OrdinalIgnoreCase) -ge 0
}

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
    $isKnownKokoroCommand = (
        $commandLine -like "*src.api.server*" -or
        $commandLine -like "*kokoro-sidecar*" -or
        $commandLine -like "*target\debug\kokoro.exe*" -or
        $commandLine -like "*vite*" -or
        $commandLine -like "*frontend:dev*" -or
        $commandLine -like "*tauri:dev*" -or
        $commandLine -like "*concurrently*" -or
        $commandLine -like "*@tauri-apps*"
    )

    if (-not $isKnownKokoroCommand) {
        return $false
    }

    return (
        (Contains-ProjectRoot -CommandLine $commandLine) -or
        $commandLine -like "*src.api.server*" -or
        $commandLine -like "*kokoro-sidecar*" -or
        $commandLine -like "*target\debug\kokoro.exe*"
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
        $children = Get-CimInstance Win32_Process | Where-Object {
            $_.Name -like "python*" -and [string]$_.CommandLine -like "*parent_pid=$ProcessId*"
        }
        foreach ($child in $children) {
            Write-Host "[kill] PID $($child.ProcessId) $($child.Name) (worker for stale PID $ProcessId)"
            Write-Host "       $($child.CommandLine)"
            if (-not $DryRun) {
                Stop-Process -Id $child.ProcessId -Force
            }
        }
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
        $children = Get-CimInstance Win32_Process | Where-Object {
            $_.ParentProcessId -eq $ProcessId -or (
                $_.Name -like "python*" -and [string]$_.CommandLine -like "*parent_pid=$ProcessId*"
            )
        }
        foreach ($child in $children) {
            Write-Host "[kill] PID $($child.ProcessId) $($child.Name) (child of PID $ProcessId)"
            Write-Host "       $($child.CommandLine)"
            Stop-Process -Id $child.ProcessId -Force
        }
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
    if (-not (Contains-ProjectRoot -CommandLine $commandLine)) {
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

$apps = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -eq "kokoro.exe" -and [string]$_.CommandLine -like "*target\debug\kokoro.exe*"
}

foreach ($app in $apps) {
    $appPid = [int]$app.ProcessId
    if ($killed.Contains($appPid)) {
        continue
    }

    Stop-KokoroProcess -ProcessId $appPid -Reason "Tauri debug app"
    [void]$killed.Add($appPid)
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
