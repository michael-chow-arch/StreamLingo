param(
    [ValidatePattern('^[a-p]{32}$')]
    [string]$ExtensionId = 'ggakbplmndfijhdcepbafoibilffbhmg'
)

$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskServer = Join-Path $taskRoot 'backend\.venv\Scripts\streamlingo-server.exe'
if (-not (Test-Path -LiteralPath $taskServer)) {
    throw 'Backend is not installed. Follow the setup commands in README.md first.'
}
& $taskServer --mode demo --allow-origin "chrome-extension://$ExtensionId"
exit $LASTEXITCODE
