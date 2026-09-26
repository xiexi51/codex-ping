[CmdletBinding()]
param([ValidateSet('status','logs','start','stop','restart','run','uninstall','pause','resume')][string]$Command = 'status')
$ErrorActionPreference = 'Stop'
$taskRoot = [Environment]::GetFolderPath('UserProfile')
$taskLib = Join-Path $taskRoot '.local\lib\codex-ping'
$taskConfig = Join-Path $taskRoot '.config\codex-ping'
$taskState = Join-Path $taskRoot '.local\state\codex-ping'
$scheduler = Join-Path $taskLib 'scheduler.py'
$runtime = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $taskConfig 'runtime.json') | ConvertFrom-Json
$runKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'

function Get-Runner {
    $pidFile = Join-Path $taskState 'scheduler.pid'
    if (-not (Test-Path -LiteralPath $pidFile)) { return $null }
    $taskProcessId = 0
    $pidText = [string](Get-Content -Raw -LiteralPath $pidFile -ErrorAction SilentlyContinue)
    if (-not [int]::TryParse($pidText, [ref]$taskProcessId) -or $taskProcessId -le 0) { return $null }
    $candidate = Get-CimInstance Win32_Process -Filter "ProcessId = $taskProcessId"
    if ($candidate -and $candidate.CommandLine -and $candidate.CommandLine.Contains($scheduler) -and
        $candidate.ExecutablePath -eq $runtime.pythonw) { return $candidate }
    return $null
}
function Enable-Autostart {
    if (-not (Test-Path -LiteralPath $runKey)) { New-Item -Path $runKey | Out-Null }
    New-ItemProperty -Path $runKey -Name 'CodexPing' -PropertyType String -Value (
        '"{0}" -X utf8 "{1}"' -f $runtime.pythonw, $scheduler) -Force | Out-Null
}
function Disable-Autostart {
    Remove-ItemProperty -Path $runKey -Name 'CodexPing' -ErrorAction SilentlyContinue
}
function Start-Runner {
    if (Get-Runner) { return }
    Remove-Item -LiteralPath (Join-Path $taskState 'stop.request') -Force -ErrorAction SilentlyContinue
    Start-Process -FilePath $runtime.pythonw -ArgumentList ('-X utf8 "{0}"' -f $scheduler) -WindowStyle Hidden -WorkingDirectory $taskLib | Out-Null
    $deadline = (Get-Date).AddSeconds(15)
    do {
        Start-Sleep -Milliseconds 200
        if (Get-Runner) { return }
    } while ((Get-Date) -lt $deadline)
    throw "Scheduler did not start. See $taskState\scheduler-error.log"
}
function Stop-Runner {
    if (-not (Get-Runner)) {
        Remove-Item -LiteralPath (Join-Path $taskState 'stop.request') -Force -ErrorAction SilentlyContinue
        return
    }
    [IO.File]::WriteAllText((Join-Path $taskState 'stop.request'), '')
    $settings = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $taskConfig 'settings.json') | ConvertFrom-Json
    $deadline = (Get-Date).AddSeconds([double]$settings.timeout_seconds + 30)
    while (Get-Runner) {
        if ((Get-Date) -ge $deadline) { throw 'Scheduler did not stop before its deadline; files have been retained.' }
        Start-Sleep -Milliseconds 250
    }
    Remove-Item -LiteralPath (Join-Path $taskState 'stop.request') -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath (Join-Path $taskState 'run.request') -Force -ErrorAction SilentlyContinue
}
switch ($Command) {
    status {
        $runner = Get-Runner
        $autostart = Get-ItemProperty -Path $runKey -Name 'CodexPing' -ErrorAction SilentlyContinue
        Write-Host ('Running: {0} | PID: {1} | Start at logon: {2}' -f [bool]$runner, $runner.ProcessId, [bool]$autostart)
        & $runtime.python -X utf8 $scheduler status
        if ($LASTEXITCODE -ne 0) { throw 'Unable to read scheduler status.' }
    }
    logs {
        $summary = Join-Path $taskState 'summary.log'
        if (-not (Test-Path -LiteralPath $summary)) { [IO.File]::WriteAllText($summary, '') }
        Get-Content -LiteralPath $summary -Encoding UTF8 -Tail 36 -Wait
    }
    start { Start-Runner; Enable-Autostart; Write-Host 'Started; autostart enabled for this user at logon.' }
    stop { Disable-Autostart; Stop-Runner; Write-Host 'Stopped; autostart disabled.' }
    restart { Stop-Runner; Start-Runner; Enable-Autostart; Write-Host 'Restarted; autostart enabled.' }
    run {
        Start-Runner
        [IO.File]::WriteAllText((Join-Path $taskState 'run.request'), '')
        Write-Host 'Immediate ping requested. Check logs for the result; the reset query follows two minutes later.'
    }
    pause { Stop-Runner }
    resume { Start-Runner }
    uninstall {
        Disable-Autostart
        Stop-Runner
        # Validate every fixed, absolute target before recursively removing task files.
        foreach ($relative in @('.local\lib\codex-ping', '.config\codex-ping', '.local\state\codex-ping')) {
            $target = [IO.Path]::GetFullPath((Join-Path $taskRoot $relative))
            $expected = $taskRoot.TrimEnd('\') + '\' + $relative
            if ($target -ne $expected -or -not $target.StartsWith($taskRoot.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) {
                throw "Unsafe uninstall target: $target"
            }
            if (Test-Path -LiteralPath $target) {
                if ((Get-Item -LiteralPath $target).Attributes -band [IO.FileAttributes]::ReparsePoint) {
                    throw "Refusing to recursively delete linked directory: $target"
                }
                Remove-Item -LiteralPath $target -Recurse -Force
            }
        }
        Remove-Item -LiteralPath (Join-Path $taskRoot '.local\bin\codex-ping.cmd') -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath (Join-Path $taskRoot '.local\bin\codex-ping.ps1') -Force
        Write-Host 'Removed codex-ping. Codex login credentials and Python were retained.'
    }
}
