param(
    [ValidatePattern('^[a-p]{32}$')]
    [string]$ExtensionId = '',
    [string]$OllamaModel = '',
    [string]$OllamaUrl = '',
    [ValidateSet('base','base.en')][string]$AsrModel = 'base',
    [switch]$Background,
    [switch]$WaitForReady
)

$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskPython = Join-Path $taskRoot 'backend\.venv\Scripts\python.exe'
$taskConfigFile = Join-Path $taskRoot '.streamlingo.json'
if (Test-Path -LiteralPath $taskConfigFile) {
    try { $taskConfig = Get-Content -LiteralPath $taskConfigFile -Raw -Encoding UTF8 | ConvertFrom-Json }
    catch { throw 'The local setup configuration is damaged. Run Setup-StreamLingo.cmd again to repair it.' }
    if ($taskConfig.version -ne 1) { throw 'The local setup configuration is not supported. Run Setup-StreamLingo.cmd again.' }
    if (-not $ExtensionId) { $ExtensionId = $taskConfig.extensionId }
    if (-not $OllamaModel) { $OllamaModel = $taskConfig.ollamaModel }
    if (-not $OllamaUrl) { $OllamaUrl = $taskConfig.ollamaUrl }
    if (-not $PSBoundParameters.ContainsKey('AsrModel') -and $taskConfig.asrModel) { $AsrModel = $taskConfig.asrModel }
}
if (-not $ExtensionId) { $ExtensionId = 'ggakbplmndfijhdcepbafoibilffbhmg' }
if (-not $OllamaModel) { throw 'No translation model is configured. Run Setup-StreamLingo.cmd to choose an existing Ollama model, or pass -OllamaModel NAME.' }
if (-not $OllamaUrl) { $OllamaUrl = 'http://127.0.0.1:11434' }
if ($ExtensionId -notmatch '^[a-p]{32}$') { throw 'Invalid extension ID. Run Setup again with your actual extension ID.' }
if ($AsrModel -notin @('base','base.en')) { throw 'Invalid speech model in setup configuration. Run Setup-StreamLingo.cmd again.' }
if ([string]::IsNullOrWhiteSpace($OllamaModel) -or $OllamaModel.Length -gt 200 -or $OllamaModel -match '[\x00-\x1f"]') {
    throw 'Invalid Ollama model name. Run Setup again to choose an installed model.'
}
$taskEndpoint = $null
if (-not [uri]::TryCreate($OllamaUrl, [UriKind]::Absolute, [ref]$taskEndpoint) -or
    $taskEndpoint.Scheme -notin @('http','https') -or -not $taskEndpoint.IsLoopback -or
    $taskEndpoint.UserInfo -or $taskEndpoint.AbsolutePath -ne '/' -or $taskEndpoint.Query -or $taskEndpoint.Fragment) {
    throw 'Ollama must use a local HTTP(S) origin, such as http://127.0.0.1:11434. Run Setup again to repair the configuration.'
}
$OllamaUrl = $OllamaUrl.TrimEnd('/')
$taskModel = Join-Path $taskRoot "models\whisper-$AsrModel"
$taskOutput = Join-Path $taskRoot 'output\service'
$taskPidFile = Join-Path $taskOutput 'process.json'
if (-not (Test-Path -LiteralPath $taskPython)) { throw 'Backend is missing. Double-click Setup-StreamLingo.cmd first.' }
foreach ($taskModelFile in @('model.bin','config.json','tokenizer.json','vocabulary.txt')) {
    $taskModelPath = Join-Path $taskModel $taskModelFile
    if (-not (Test-Path -LiteralPath $taskModelPath -PathType Leaf) -or (Get-Item -LiteralPath $taskModelPath).Length -eq 0) {
        throw "Speech model is incomplete (missing or empty $taskModelFile): $taskModel. Run Setup-StreamLingo.cmd to resume the download."
    }
}
if (Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue) {
    try { $taskExisting = Invoke-RestMethod 'http://127.0.0.1:8765/health' -TimeoutSec 5 }
    catch { throw 'Port 8765 is occupied by another or unresponsive service. Close it and start StreamLingo again.' }
    if ($taskExisting.protocol_version -eq 1 -and $taskExisting.mode -eq 'whisperlivekit' -and $taskExisting.status -eq 'ready') {
        if ($taskExisting.translation -ne 'configured' -or ($AsrModel -eq 'base' -and @($taskExisting.source_languages) -notcontains 'auto')) {
            throw 'A service is running with an older model/configuration. Stop it using Stop-StreamLingo.cmd, then start again to enable the selected translation modes.'
        }
        Write-Output 'StreamLingo is already running. Open YouTube and click Start subtitles in the extension.'
        Write-Output 'To apply a model/configuration change, double-click Stop-StreamLingo.cmd, then Start-StreamLingo.cmd.'
        exit 0
    }
    throw 'The subtitle service is already starting, in demo mode, or has failed. Run Doctor-StreamLingo.cmd for details; do not start a second copy.'
}
try { $taskTags = Invoke-RestMethod "$($OllamaUrl.TrimEnd('/'))/api/tags" -TimeoutSec 10 }
catch { throw 'Ollama is not reachable. Start your existing Ollama app, then start StreamLingo again.' }
if (@($taskTags.models | ForEach-Object { $_.name }) -notcontains $OllamaModel) {
    throw "Ollama model '$OllamaModel' is unavailable. Run Setup-StreamLingo.cmd to select an installed model."
}
try {
    $taskShow = Invoke-RestMethod "$OllamaUrl/api/show" -Method Post -ContentType 'application/json; charset=utf-8' `
        -Body ([Text.Encoding]::UTF8.GetBytes((@{ model = $OllamaModel; verbose = $false } | ConvertTo-Json))) -TimeoutSec 10
} catch { throw 'The configured Ollama model could not be inspected. Start or update your existing Ollama app, then rerun Setup.' }
if (@($taskShow.capabilities) -notcontains 'completion') {
    throw "Ollama model '$OllamaModel' does not report text completion support. Embedding-only models cannot translate; rerun Setup to choose a chat model."
}
$taskArguments = @('-m', 'streamlingo.cli', '--mode', 'whisperlivekit', '--model', $AsrModel,
    '--model-dir', $taskModel, '--ollama-model', $OllamaModel, '--ollama-url', $OllamaUrl,
    '--allow-origin', "chrome-extension://$ExtensionId")
if (-not $Background) {
    & $taskPython @taskArguments
    exit $LASTEXITCODE
}

# Start-Process joins ArgumentList into one Windows command line. Quote each
# value and reject embedded quotes so paths with spaces remain single arguments.
foreach ($taskArgument in $taskArguments) {
    if ($taskArgument.Contains('"') -or $taskArgument.Contains("`r") -or $taskArgument.Contains("`n")) {
        throw 'Launcher arguments cannot contain quotes or newlines.'
    }
}
$taskQuotedArguments = $taskArguments | ForEach-Object { '"' + $_ + '"' }
New-Item -ItemType Directory -Path $taskOutput -Force | Out-Null
$taskProcess = Start-Process -FilePath $taskPython -ArgumentList $taskQuotedArguments -WorkingDirectory $taskRoot `
    -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $taskOutput 'stdout.log') `
    -RedirectStandardError (Join-Path $taskOutput 'stderr.log')
try { $taskStartedUtc = $taskProcess.StartTime.ToUniversalTime().ToString('o') }
catch { throw "The service exited immediately. See $taskOutput\stderr.log." }
$taskTemporaryPidFile = "$taskPidFile.tmp"
@{ pid = $taskProcess.Id; startedUtc = $taskStartedUtc; python = $taskPython } |
    ConvertTo-Json | Set-Content -LiteralPath $taskTemporaryPidFile -Encoding utf8
Move-Item -LiteralPath $taskTemporaryPidFile -Destination $taskPidFile -Force
Write-Output "StreamLingo started (PID $($taskProcess.Id)); models may still be loading."
Write-Output 'Health: http://127.0.0.1:8765/health'
Write-Output "Logs: $taskOutput"
Write-Output 'Stop: .\scripts\stop.ps1'
if ($WaitForReady) {
    $taskDeadline = (Get-Date).AddSeconds(120)
    do {
        if (-not (Get-Process -Id $taskProcess.Id -ErrorAction SilentlyContinue)) { throw "The service stopped while loading. See $taskOutput\stderr.log." }
        $taskHealth = $null
        try {
            $taskHealth = Invoke-RestMethod 'http://127.0.0.1:8765/health' -TimeoutSec 3
        } catch { # A refused connection is normal until Uvicorn finishes startup.
            $taskHealth = $null
        }
        if ($taskHealth) {
            if ($taskHealth.protocol_version -ne 1 -or $taskHealth.mode -ne 'whisperlivekit') {
                throw 'Port 8765 responded with another service. Inspect output/service/stderr.log or run Doctor-StreamLingo.cmd.'
            }
            if ($taskHealth.status -eq 'ready') {
                Write-Output 'Ready. Open YouTube, choose a translation mode, and click Start subtitles in StreamLingo.'
                exit 0
            }
            if ($taskHealth.status -eq 'error') { throw "Speech model loading failed. See $taskOutput\stderr.log or run Doctor-StreamLingo.cmd." }
        }
        Start-Sleep -Seconds 2
    } while ((Get-Date) -lt $taskDeadline)
    throw 'The service is still loading after 2 minutes. Run Doctor-StreamLingo.cmd to check progress before starting another copy.'
}
