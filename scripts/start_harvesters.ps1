<#
Start the JobThai and JobBKK harvesters (each in its own minimized cmd window) if they are not
already running. Progress is kept in data/*.sqlite, so starting again continues where it stopped.

  powershell -ExecutionPolicy Bypass -File scripts\start_harvesters.ps1          # start what is missing, once
  powershell -ExecutionPolicy Bypass -File scripts\start_harvesters.ps1 -Watch   # keep checking every 2 minutes
  powershell -ExecutionPolicy Bypass -File scripts\start_harvesters.ps1 -Status  # only show status + last log lines

Never starts a second copy of a harvester (two copies = two requests at once, against AGENTS.md).
#>
param([switch]$Watch, [switch]$Status)

$root = Split-Path -Parent $PSScriptRoot
$harvesters = @(
    @{ Name = 'jobthai'; Script = 'jobthai_harvester.py'; Bat = 'run_jobthai.bat'; Log = 'data\harvester.log' },
    @{ Name = 'jobbkk';  Script = 'jobbkk_harvester.py';  Bat = 'run_jobbkk.bat';  Log = 'data\harvester_jobbkk.log' }
)

function Get-Running($h) {
    # the python process OR its restart loop (the .bat waits 60 s between restarts)
    Get-CimInstance Win32_Process -Filter "Name='python.exe' or Name='cmd.exe'" |
        Where-Object { $_.CommandLine -and ($_.CommandLine -like "*$($h.Script)*" -or $_.CommandLine -like "*$($h.Bat)*") }
}

function Show-Status {
    foreach ($h in $harvesters) {
        $state = if (Get-Running $h) { 'RUNNING' } else { 'STOPPED' }
        $last = ''
        $logPath = Join-Path $root $h.Log
        if (Test-Path $logPath) { $last = (Get-Content $logPath -Tail 1 -Encoding UTF8) }
        Write-Host ("{0,-8} {1,-8} {2}" -f $h.Name, $state, $last)
    }
}

function Start-Missing {
    foreach ($h in $harvesters) {
        if (Get-Running $h) { continue }
        $bat = Join-Path $root "scraper\$($h.Bat)"
        Start-Process -FilePath 'cmd.exe' -ArgumentList '/c', "`"$bat`"" -WorkingDirectory $root -WindowStyle Minimized
        Write-Host ("{0:HH:mm:ss} started {1} (window minimized - do not click inside it or close it)" -f (Get-Date), $h.Name)
    }
}

if ($Status) { Show-Status; return }

do {
    Start-Missing
    if ($Watch) { Start-Sleep -Seconds 120 }
} while ($Watch)

Start-Sleep -Seconds 3
Show-Status
