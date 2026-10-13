param(
    [string]$OllamaModel = '',
    [string]$OllamaUrl = 'http://127.0.0.1:11434',
    [ValidatePattern('^[a-p]{32}$')][string]$ExtensionId = 'ggakbplmndfijhdcepbafoibilffbhmg',
    [switch]$NonInteractive
)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskVenvPython = Join-Path $taskRoot 'backend\.venv\Scripts\python.exe'
$taskConfigFile = Join-Path $taskRoot '.streamlingo.json'

function Assert-Exit([string]$Step) {
    if ($LASTEXITCODE -ne 0) { throw "$Step failed (exit $LASTEXITCODE). Correct the error above and run Setup again; completed downloads are reused." }
}
function Test-Python([string]$Exe, [string[]]$Prefix = @()) {
    if (-not (Get-Command $Exe -ErrorAction SilentlyContinue)) { return $false }
    try {
        & $Exe @Prefix -c 'import sys; sys.exit(0 if (3,11) <= sys.version_info[:2] < (3,14) and sys.maxsize > 2**32 else 1)' 2>$null
        return $LASTEXITCODE -eq 0
    } catch { return $false }
}

Write-Host 'StreamLingo setup - for users who already have Ollama.'
Write-Host 'This prepares the local subtitle service and speech model. It does not install or change Ollama models.'
Write-Host 'Real speech recognition requires 64-bit Python 3.11-3.13, an NVIDIA GPU, CUDA 12, and cuDNN 9.'
Write-Host 'Runtime requirements: docs/runtime-requirements.md. Setup does not install GPU drivers or CUDA/cuDNN libraries.'
$taskPrevious = $null
if (Test-Path -LiteralPath $taskConfigFile) {
    try { $taskPrevious = Get-Content -LiteralPath $taskConfigFile -Raw -Encoding UTF8 | ConvertFrom-Json }
    catch { Write-Host 'Existing setup configuration could not be read; choose a model again.' }
}
if ($taskPrevious) {
    if (-not $PSBoundParameters.ContainsKey('OllamaUrl') -and $taskPrevious.ollamaUrl) { $OllamaUrl = $taskPrevious.ollamaUrl }
    if (-not $PSBoundParameters.ContainsKey('ExtensionId') -and $taskPrevious.extensionId) { $ExtensionId = $taskPrevious.extensionId }
}
if ($ExtensionId -notmatch '^[a-p]{32}$') { throw 'Invalid extension ID. Pass -ExtensionId with the 32-letter ID shown in chrome://extensions.' }
$taskEndpoint = $null
if (-not [uri]::TryCreate($OllamaUrl, [UriKind]::Absolute, [ref]$taskEndpoint) -or
    $taskEndpoint.Scheme -notin @('http','https') -or -not $taskEndpoint.IsLoopback -or
    $taskEndpoint.UserInfo -or $taskEndpoint.AbsolutePath -ne '/' -or $taskEndpoint.Query -or $taskEndpoint.Fragment) {
    throw 'The installer accepts only a local Ollama origin, such as http://127.0.0.1:11434.'
}
$OllamaUrl = $OllamaUrl.TrimEnd('/')
try { $taskTags = Invoke-RestMethod "$OllamaUrl/api/tags" -TimeoutSec 10 }
catch { throw "Ollama is not reachable at $OllamaUrl. Start your existing Ollama app, then run Setup again." }
$taskInstalledModels = @($taskTags.models | ForEach-Object { $_.name } | Where-Object { $_ -is [string] -and $_.Trim() } | Sort-Object -Unique)
if ($taskInstalledModels.Count -eq 0) { throw 'Ollama has no installed models. Add a text/chat model in Ollama, then run Setup again.' }
if ($OllamaModel -and $taskInstalledModels -notcontains $OllamaModel) { throw "Model '$OllamaModel' is not installed in Ollama." }
$taskModels = @()
foreach ($taskName in $taskInstalledModels) {
    # /api/show reads metadata; it neither loads nor pulls a model. Completion
    # capability excludes embedding-only models without guessing their names.
    try {
        $taskShow = Invoke-RestMethod "$OllamaUrl/api/show" -Method Post -ContentType 'application/json; charset=utf-8' `
            -Body ([Text.Encoding]::UTF8.GetBytes((@{ model = $taskName; verbose = $false } | ConvertTo-Json))) -TimeoutSec 10
        if (@($taskShow.capabilities) -contains 'completion') { $taskModels += $taskName }
        else { Write-Host "Skipping '$taskName': no text completion capability reported by Ollama." }
    } catch { Write-Warning "Cannot inspect '$taskName'; it will not be selected. Check the installed Ollama version and try again." }
}
if ($taskModels.Count -eq 0) { throw 'No installed text completion model was found. Embedding-only models cannot translate. If model capabilities are missing, update your existing Ollama app and rerun Setup.' }
if (-not $OllamaModel -and $taskPrevious -and $taskModels -contains $taskPrevious.ollamaModel) { $OllamaModel = $taskPrevious.ollamaModel }
if (-not $OllamaModel) {
    if ($taskModels -contains 'qwen3.5:9b') { $OllamaModel = 'qwen3.5:9b' }
    elseif ($taskModels.Count -eq 1) { $OllamaModel = $taskModels[0] }
    elseif ($NonInteractive) { throw 'Multiple Ollama models are installed. Run Setup interactively or pass -OllamaModel NAME.' }
    else {
        Write-Host 'Choose an installed text/chat model for translation:'
        for ($taskIndex = 0; $taskIndex -lt $taskModels.Count; $taskIndex++) { Write-Host "$($taskIndex + 1). $($taskModels[$taskIndex])" }
        $taskChoice = 0
        if (-not [int]::TryParse((Read-Host 'Model number'), [ref]$taskChoice) -or $taskChoice -lt 1 -or $taskChoice -gt $taskModels.Count) {
            throw 'Invalid model number. Run Setup again to select a model.'
        }
        $OllamaModel = $taskModels[$taskChoice - 1]
    }
}
if ($taskModels -notcontains $OllamaModel) { throw "Model '$OllamaModel' does not report text completion support. Select an installed text/chat model." }
Write-Host "Translation model: $OllamaModel"

# Source checkouts are always rebuilt, even if the version number is unchanged.
# Release bundles omit extension/src and must contain a complete built extension.
$taskSourceCheckout = Test-Path -LiteralPath (Join-Path $taskRoot 'extension\src') -PathType Container
if ($taskSourceCheckout) {
    if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue) -or -not (Get-Command node.exe -ErrorAction SilentlyContinue)) {
        throw 'A source checkout requires Node.js 22+. Install it and rerun Setup, or use the Windows release bundle (no Node required).'
    }
    $taskNodeVersion = & node.exe -p 'process.versions.node'
    Assert-Exit 'Node.js version check'
    if ([version]$taskNodeVersion -lt [version]'22.0') { throw 'A source checkout requires Node.js 22 or newer. The Windows release bundle does not require Node.' }
} else {
    $taskManifest = Join-Path $taskRoot 'dist\extension\manifest.json'
    if (-not (Test-Path -LiteralPath $taskManifest -PathType Leaf)) { throw 'This bundle is incomplete: dist/extension is missing. Extract the complete Windows release ZIP and rerun Setup.' }
    try {
        $taskBuiltVersion = (Get-Content -LiteralPath $taskManifest -Raw -Encoding UTF8 | ConvertFrom-Json).version
        $taskReleaseVersion = (Get-Content -LiteralPath (Join-Path $taskRoot 'package.json') -Raw -Encoding UTF8 | ConvertFrom-Json).version
    } catch { throw 'The release manifest could not be read. Extract the complete Windows release ZIP again.' }
    if (-not $taskBuiltVersion -or $taskBuiltVersion -ne $taskReleaseVersion) { throw 'The built extension version does not match this release. Extract the complete Windows release ZIP again.' }
    foreach ($taskAsset in @('background.js','popup.html','popup.js','popup.css','offscreen.html','offscreen.js','content.js','pcm-worklet.js',
                             '_locales\en\messages.json','_locales\zh_CN\messages.json','icons\icon16.png','icons\icon32.png','icons\icon48.png','icons\icon128.png')) {
        if (-not (Test-Path -LiteralPath (Join-Path $taskRoot "dist\extension\$taskAsset") -PathType Leaf)) { throw "This bundle is incomplete: missing extension file '$taskAsset'. Extract the complete Windows release ZIP again." }
    }
}

if (-not (Test-Python $taskVenvPython)) {
    $taskPython = $null; $taskPythonPrefix = @()
    foreach ($taskVersion in @('-3.12', '-3.11', '-3.13')) {
        if (Test-Python 'py' @($taskVersion)) { $taskPython = 'py'; $taskPythonPrefix = @($taskVersion); break }
    }
    if (-not $taskPython -and (Test-Python 'python')) { $taskPython = 'python' }
    $taskStandardPython = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'
    if (-not $taskPython -and (Test-Python $taskStandardPython)) { $taskPython = $taskStandardPython }
    if (-not $taskPython) {
        if ($NonInteractive -or -not (Get-Command winget -ErrorAction SilentlyContinue)) {
            throw '64-bit Python 3.11-3.13 is required. Install 64-bit Python 3.12 from https://www.python.org/downloads/ and run Setup again.'
        }
        $taskInstall = Read-Host '64-bit Python is missing. Install Python 3.12 using Windows Package Manager? [y/N]'
        if ($taskInstall -notmatch '^[yY]$') { throw 'Setup stopped. Install 64-bit Python 3.12 and run Setup again.' }
        & winget install --id Python.Python.3.12 --exact --source winget
        Assert-Exit 'Python installation'
        if (Test-Python $taskStandardPython) { $taskPython = $taskStandardPython }
        else { throw 'Python was installed. Close this window and run Setup again to refresh the executable search path.' }
    }
    if (Test-Path -LiteralPath (Join-Path $taskRoot 'backend\.venv')) {
        throw 'The existing backend virtual environment needs 64-bit Python 3.11-3.13. Preserve it or rename backend/.venv before rerunning Setup.'
    }
    & $taskPython @taskPythonPrefix -m venv (Join-Path $taskRoot 'backend\.venv')
    Assert-Exit 'Virtual environment creation'
}
Write-Host 'Installing the subtitle service and speech dependencies. The first download can be large.'
& $taskVenvPython -m pip install -e "$(Join-Path $taskRoot 'backend')[asr]"
Assert-Exit 'Backend dependency installation'
& $taskVenvPython (Join-Path $PSScriptRoot 'download-model.py')
Assert-Exit 'Multilingual speech model download'

if ($taskSourceCheckout) {
    Push-Location $taskRoot
    try { & npm.cmd ci; Assert-Exit 'npm install'; & npm.cmd run build; Assert-Exit 'Extension build' }
    finally { Pop-Location }
}
$taskTemporaryConfig = "$taskConfigFile.tmp"
@{ version = 1; ollamaUrl = $OllamaUrl; ollamaModel = $OllamaModel; extensionId = $ExtensionId; asrModel = 'base' } |
    ConvertTo-Json | Set-Content -LiteralPath $taskTemporaryConfig -Encoding utf8
Move-Item -LiteralPath $taskTemporaryConfig -Destination $taskConfigFile -Force
Write-Host ''
Write-Host 'Setup complete. Next time, double-click Start-StreamLingo.cmd.'
Write-Host 'First use: open chrome://extensions, enable Developer mode, and Load unpacked:'
Write-Host (Join-Path $taskRoot 'dist\extension')
Write-Host 'The source/release bundle is a manual installation; a Chrome Web Store listing is not published yet.'
