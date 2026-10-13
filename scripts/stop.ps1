$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskPidFile = Join-Path $taskRoot 'output\service\process.json'
if (-not (Test-Path -LiteralPath $taskPidFile)) {
    Write-Output 'No background service was started by scripts\start.ps1.'
    exit 0
}
$taskRecordText = Get-Content -LiteralPath $taskPidFile -Raw -Encoding UTF8
try { $taskRecord = $taskRecordText | ConvertFrom-Json }
catch { throw 'The service PID record is damaged. Nothing was stopped. Inspect output/service/process.json or run Doctor-StreamLingo.cmd.' }
$taskRecordedPid = 0
if (-not [int]::TryParse([string]$taskRecord.pid, [ref]$taskRecordedPid) -or $taskRecordedPid -le 0) {
    throw 'The service PID record is invalid. Nothing was stopped.'
}
$taskExpectedPython = Join-Path $taskRoot 'backend\.venv\Scripts\python.exe'
if (-not $taskRecord.python -or [IO.Path]::GetFullPath($taskRecord.python) -ne [IO.Path]::GetFullPath($taskExpectedPython)) {
    throw 'The PID record belongs to a different installation. Nothing was stopped.'
}
function Remove-StaleRecord {
    # A concurrent new start may have replaced the file; never remove its record.
    if ((Test-Path -LiteralPath $taskPidFile) -and (Get-Content -LiteralPath $taskPidFile -Raw -Encoding UTF8) -eq $taskRecordText) {
        Remove-Item -LiteralPath $taskPidFile
    }
}
$taskProcess = Get-Process -Id $taskRecord.pid -ErrorAction SilentlyContinue
if (-not $taskProcess) { Remove-StaleRecord; Write-Output 'The background service has already stopped.'; exit 0 }
$taskDetails = Get-CimInstance Win32_Process -Filter "ProcessId = $($taskProcess.Id)"
try { $taskRecordedUtc = ([DateTimeOffset]$taskRecord.startedUtc).UtcDateTime }
catch { throw 'The service start-time record is invalid. Nothing was stopped.' }
$taskSameStart = [Math]::Abs(($taskProcess.StartTime.ToUniversalTime() - $taskRecordedUtc).TotalSeconds) -lt 1
if (-not $taskSameStart -or $taskDetails.ExecutablePath -ne $taskRecord.python -or $taskDetails.CommandLine -notmatch '(?:^|\s)"?-m"?\s+"?streamlingo\.cli"?(?:\s|$)') {
    throw 'The recorded PID no longer identifies this StreamLingo service. Nothing was stopped.'
}
# Windows venv's python.exe is a redirector; its child runs the interpreter.
# Stop only a direct Python child with the identical launch command, then the
# validated redirector, so no unrelated Python/Ollama process is affected.
$taskChildren = Get-CimInstance Win32_Process -Filter "ParentProcessId = $($taskProcess.Id)"
foreach ($taskChild in $taskChildren) {
    if ($taskChild.Name -eq 'python.exe' -and $taskChild.CommandLine -eq $taskDetails.CommandLine) {
        Stop-Process -Id $taskChild.ProcessId -ErrorAction SilentlyContinue
    }
}
Stop-Process -Id $taskProcess.Id -ErrorAction SilentlyContinue
if (Get-Process -Id $taskProcess.Id -ErrorAction SilentlyContinue) { throw 'The service did not stop. Check your permissions and run Stop again.' }
Remove-StaleRecord
Write-Output 'StreamLingo stopped. Ollama is unchanged.'
