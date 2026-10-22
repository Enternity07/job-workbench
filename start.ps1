$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$bundledPython = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
Write-Host 'Open http://127.0.0.1:8765 after the server starts. Press Ctrl+C to stop.'
if (Test-Path -LiteralPath $bundledPython) {
    & $bundledPython app.py
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 app.py
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    & python app.py
} else {
    Write-Host 'Python 3.10+ is required. Install Python, then run this file again.'
}
Read-Host 'Press Enter to close'
