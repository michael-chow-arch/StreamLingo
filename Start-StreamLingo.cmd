@echo off
setlocal
pushd "%~dp0" || exit /b 1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start.ps1" -Background -WaitForReady %*
set "streamlingoExitCode=%errorlevel%"
pause
popd
exit /b %streamlingoExitCode%
