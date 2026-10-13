$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskProblems = 0
function Show-Check([string]$Name, [bool]$Ok, [string]$Detail) {
    if ($Ok) { Write-Host "[OK] $Name - $Detail" }
    else { Write-Host "[CHECK] $Name - $Detail"; $script:taskProblems++ }
}
Write-Host 'StreamLingo local diagnostics (nothing is uploaded).'
$taskPython = Join-Path $taskRoot 'backend\.venv\Scripts\python.exe'
$taskHasPython = Test-Path -LiteralPath $taskPython -PathType Leaf
Show-Check 'Python environment' $taskHasPython 'Setup-StreamLingo.cmd prepares backend/.venv'
if ($taskHasPython) {
    try {
        # This entry point only inspects runtime files. It does not import the
        # inference engine, initialize CUDA, load a model, or alter the machine.
        $taskRuntimeLines = @(& $taskPython -m streamlingo.runtime_requirements 2>&1)
        $taskRuntimeExit = $LASTEXITCODE
        $taskRuntime = ($taskRuntimeLines -join "`n") | ConvertFrom-Json
        if ($taskRuntime -isnot [pscustomobject] -or
            $taskRuntime.platform -isnot [string] -or [string]::IsNullOrWhiteSpace($taskRuntime.platform) -or
            $taskRuntime.message -isnot [string] -or [string]::IsNullOrWhiteSpace($taskRuntime.message) -or
            $taskRuntime.missing_dlls -isnot [array] -or
            @($taskRuntime.missing_dlls | Where-Object { $_ -isnot [string] -or [string]::IsNullOrWhiteSpace($_) }).Count -gt 0) {
            throw 'Invalid runtime-check JSON response.'
        }
        if ($taskRuntimeExit -eq 0 -and $taskRuntime.missing_dlls.Count -eq 0 -and
            (($taskRuntime.status -eq 'ok' -and $taskRuntime.platform -eq 'win32') -or
             ($taskRuntime.status -eq 'not_applicable' -and $taskRuntime.platform -ne 'win32'))) {
            Show-Check 'Speech runtime files' $true $taskRuntime.message
        } elseif ($taskRuntimeExit -eq 2 -and $taskRuntime.status -eq 'missing' -and
                  $taskRuntime.platform -eq 'win32' -and $taskRuntime.missing_dlls.Count -gt 0) {
            Show-Check 'Speech runtime files' $false ($taskRuntime.message + ' Missing DLLs: ' + ($taskRuntime.missing_dlls -join ', '))
        } else {
            throw "Unexpected runtime-check status or exit code ($taskRuntimeExit)."
        }
    } catch {
        Show-Check 'Speech runtime files' $false ("Could not validate the read-only runtime check. Run Setup-StreamLingo.cmd to update the backend and see docs/runtime-requirements.md. " + $_.Exception.Message)
    }
}
Show-Check 'Multilingual speech model' (Test-Path -LiteralPath (Join-Path $taskRoot 'models\whisper-base\model.bin')) 'models/whisper-base'
Show-Check 'Built extension' (Test-Path -LiteralPath (Join-Path $taskRoot 'dist\extension\manifest.json')) 'Load dist/extension in Chrome'
$taskConfig = $null
try { $taskConfig = Get-Content -LiteralPath (Join-Path $taskRoot '.streamlingo.json') -Raw | ConvertFrom-Json }
catch { Show-Check 'Setup configuration' $false 'Run Setup-StreamLingo.cmd first' }
if ($taskConfig) {
    try {
        $taskTags = Invoke-RestMethod "$($taskConfig.ollamaUrl.TrimEnd('/'))/api/tags" -TimeoutSec 5
        $taskFound = @($taskTags.models | ForEach-Object { $_.name }) -contains $taskConfig.ollamaModel
        Show-Check 'Ollama model' $taskFound $taskConfig.ollamaModel
    } catch { Show-Check 'Ollama connection' $false 'Start your existing Ollama app, then retry' }
    Write-Host "Allowed extension ID: $($taskConfig.extensionId)"
}
try {
    $taskHealth = Invoke-RestMethod 'http://127.0.0.1:8765/health' -TimeoutSec 5
    $taskReady = $taskHealth.status -eq 'ready' -and $taskHealth.protocol_version -eq 1 -and $taskHealth.mode -eq 'whisperlivekit'
    Show-Check 'Subtitle service' $taskReady "$($taskHealth.mode), $($taskHealth.status)"
    Show-Check 'Translation configured' ($taskHealth.translation -eq 'configured') 'Ollama connection is checked separately above'
    Show-Check 'Four translation modes' (@($taskHealth.source_languages) -contains 'auto' -and @($taskHealth.source_languages) -contains 'zh' -and @($taskHealth.target_languages) -contains 'en') 'Requires multilingual base, not base.en'
} catch { Show-Check 'Subtitle service' $false 'Not responding on 127.0.0.1:8765; double-click Start-StreamLingo.cmd' }
Write-Host "Logs, if the service has run: $(Join-Path $taskRoot 'output\service')"
Write-Host 'No logs or audio are uploaded. Review logs before sharing them with a maintainer.'
if ($taskProblems -eq 0) { Write-Host 'All checks passed.'; exit 0 }
Write-Host "$taskProblems check(s) need attention. Follow the messages above and rerun Doctor."
exit 1
