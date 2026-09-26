$ErrorActionPreference = 'Stop'
$tokens = $null
$errors = $null
$manager = Join-Path (Split-Path $PSScriptRoot) 'bin\codex-ping.ps1'
$ast = [System.Management.Automation.Language.Parser]::ParseFile($manager, [ref]$tokens, [ref]$errors)
if ($errors) { throw ($errors | Out-String) }
$functionAst = $ast.Find({ param($node)
    $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Get-Runner'
}, $true)
# Load only the process lookup function; never run the installed manager or touch autostart.
. ([scriptblock]::Create($functionAst.Extent.Text))
$taskState = Join-Path ([IO.Path]::GetTempPath()) ('codex-ping-test-' + [guid]::NewGuid().ToString())
New-Item -ItemType Directory -Path $taskState | Out-Null
$pidFile = Join-Path $taskState 'scheduler.pid'
$scheduler = 'C:\fake\scheduler.py'
$runtime = [pscustomobject]@{ pythonw = 'C:\fake\pythonw.exe' }
function Get-CimInstance {
    param($ClassName, $Filter)
    if ($Filter -ne 'ProcessId = 123') { throw "Unexpected lookup: $Filter" }
    return [pscustomobject]@{ ProcessId = 123; CommandLine = 'pythonw.exe "C:\fake\scheduler.py"'; ExecutablePath = 'C:\fake\pythonw.exe' }
}
try {
    if ($null -ne (Get-Runner)) { throw 'Missing PID should return null' }
    foreach ($value in @('', ' ', 'invalid', '-1', '0')) {
        [IO.File]::WriteAllText($pidFile, $value)
        if ($null -ne (Get-Runner)) { throw "Invalid PID accepted: $value" }
    }
    [IO.File]::WriteAllText($pidFile, '123')
    if ((Get-Runner).ProcessId -ne 123) { throw 'Valid runner was not detected' }
    $runtime.pythonw = 'C:\other\pythonw.exe'
    if ($null -ne (Get-Runner)) { throw 'Unrelated executable was accepted' }
    Write-Output 'Windows manager PID tests passed.'
} finally {
    # Remove only the test file and its now-empty directory; no recursive deletion.
    if (Test-Path -LiteralPath $pidFile) { Remove-Item -LiteralPath $pidFile -Force }
    Remove-Item -LiteralPath $taskState
}
