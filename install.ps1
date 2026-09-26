[CmdletBinding()]
param(
    [string]$CodexBin,
    [string]$PythonBin,
    [switch]$Start
)
$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT') { throw 'Use install.sh on Linux.' }

if (-not $PythonBin) {
    foreach ($name in @('python.exe', 'python3.exe')) {
        $candidate = Get-Command $name -ErrorAction SilentlyContinue
        if ($candidate -and $candidate.Source -notlike '*\WindowsApps\*') {
            $PythonBin = $candidate.Source
            break
        }
    }
    if (-not $PythonBin -and (Get-Command py.exe -ErrorAction SilentlyContinue)) {
        $PythonBin = & py.exe -3 -c 'import sys; print(sys.executable)'
    }
}
if (-not $PythonBin) { throw 'Python 3.8+ is required. Pass -PythonBin C:\path\python.exe.' }
$PythonBin = (Resolve-Path -LiteralPath $PythonBin).Path
& $PythonBin -c 'import sys; sys.exit(0 if sys.version_info >= (3,8) else 1)'
if ($LASTEXITCODE -ne 0) { throw 'Python 3.8+ is required.' }
$pythonWindowless = Join-Path (Split-Path $PythonBin) 'pythonw.exe'
if (-not (Test-Path -LiteralPath $pythonWindowless)) { throw 'pythonw.exe must be next to python.exe.' }

if (-not $CodexBin) {
    $candidate = Get-Command codex.exe -ErrorAction SilentlyContinue
    if ($candidate) { $CodexBin = $candidate.Source }
}
if (-not $CodexBin) { throw 'Pass -CodexBin with the native Codex executable path.' }
$CodexBin = (Resolve-Path -LiteralPath $CodexBin).Path
if ([IO.Path]::GetExtension($CodexBin) -ne '.exe') { throw 'Supply native codex.exe, not an npm wrapper.' }
$helpText = (& $CodexBin exec --help | Out-String)
if ($LASTEXITCODE -ne 0 -or $helpText -notmatch '--ignore-user-config' -or $helpText -notmatch '--ignore-rules') {
    throw 'This Codex version lacks the required exec flags. See docs/windows.md.'
}

$taskRoot = [Environment]::GetFolderPath('UserProfile')
$taskLib = Join-Path $taskRoot '.local\lib\codex-ping'
$taskConfig = Join-Path $taskRoot '.config\codex-ping'
$taskState = Join-Path $taskRoot '.local\state\codex-ping'
$taskBin = Join-Path $taskRoot '.local\bin'
$manager = Join-Path $taskBin 'codex-ping.ps1'
$wasRunning = $false
if (Test-Path -LiteralPath (Join-Path $taskState 'scheduler.pid')) {
    $taskProcessId = 0
    $pidText = [string](Get-Content -Raw -LiteralPath (Join-Path $taskState 'scheduler.pid') -ErrorAction SilentlyContinue)
    if ([int]::TryParse($pidText, [ref]$taskProcessId) -and $taskProcessId -gt 0) {
        $oldProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $taskProcessId"
        $wasRunning = $oldProcess -and $oldProcess.CommandLine -and $oldProcess.CommandLine.Contains((Join-Path $taskLib 'scheduler.py'))
    }
}
if ($wasRunning) { & $manager pause }

foreach ($directory in @($taskLib, $taskConfig, $taskState, $taskBin, (Join-Path $taskState 'work'))) {
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
}
Copy-Item -Path (Join-Path $PSScriptRoot 'src\*.py') -Destination $taskLib -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'bin\codex-ping.ps1') -Destination $manager -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'bin\codex-ping.cmd') -Destination $taskBin -Force
foreach ($pair in @(@('settings.example.json', 'settings.json'), @('instructions.txt', 'instructions.txt'))) {
    $destination = Join-Path $taskConfig $pair[1]
    if (-not (Test-Path -LiteralPath $destination)) {
        Copy-Item -LiteralPath (Join-Path (Join-Path $PSScriptRoot 'config') $pair[0]) -Destination $destination
    }
}
$pinnedCodex = Join-Path $taskLib 'codex.exe'
if ($CodexBin -ne $pinnedCodex) { Copy-Item -LiteralPath $CodexBin -Destination $pinnedCodex -Force }
Get-ChildItem -LiteralPath (Split-Path $CodexBin) -Filter 'codex-*.exe' | ForEach-Object {
    $destination = Join-Path $taskLib $_.Name
    if ($_.FullName -ne $destination) { Copy-Item -LiteralPath $_.FullName -Destination $destination -Force }
}
$runtimeFile = Join-Path $taskConfig 'runtime.json'
$codexAuthHome = Join-Path $taskRoot '.codex'
if (Test-Path -LiteralPath $runtimeFile) {
    $codexAuthHome = (Get-Content -Raw -Encoding UTF8 -LiteralPath $runtimeFile | ConvertFrom-Json).codex_home
} elseif ($env:CODEX_HOME) {
    $codexAuthHome = [IO.Path]::GetFullPath($env:CODEX_HOME)
}
@{ python = $PythonBin; pythonw = $pythonWindowless; codex_home = $codexAuthHome } |
    ConvertTo-Json | Set-Content -Encoding UTF8 -LiteralPath $runtimeFile
Write-Host "Installed. Configuration and schedule preserved. Manage with: $manager"
if ($Start) { & $manager start } elseif ($wasRunning) { & $manager resume }
