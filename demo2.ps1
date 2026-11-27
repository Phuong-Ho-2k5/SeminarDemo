# One command: .\demo2.ps1
$ErrorActionPreference = 'Stop'
$previousEncoding = [Console]::OutputEncoding
$demoExit = 1
try {
    [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding
    & python -X utf8 -u (Join-Path $PSScriptRoot 'scripts/run_local_demo.py') state
    $demoExit = $LASTEXITCODE
} finally {
    [Console]::OutputEncoding = $previousEncoding
}
exit $demoExit
